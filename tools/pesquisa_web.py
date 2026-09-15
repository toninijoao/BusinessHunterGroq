import re
import json
import time
import requests


OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

USER_AGENT = (
    "BusinessHunter/1.0 "
    "(ferramenta de descoberta de empresas)"
)


MAPEAMENTO_CATEGORIAS = {
    "restaurante": ['["amenity"="restaurant"]'],
    "restaurantes": ['["amenity"="restaurant"]'],

    "café": ['["amenity"="cafe"]'],
    "cafés": ['["amenity"="cafe"]'],
    "cafe": ['["amenity"="cafe"]'],

    "bar": ['["amenity"="bar"]'],
    "bares": ['["amenity"="bar"]'],

    "lanchonete": ['["amenity"="fast_food"]'],
    "lanchonetes": ['["amenity"="fast_food"]'],

    "farmácia": ['["amenity"="pharmacy"]'],
    "farmácias": ['["amenity"="pharmacy"]'],

    "hotel": ['["tourism"="hotel"]'],
    "hotéis": ['["tourism"="hotel"]'],

    "academia": ['["leisure"="fitness_centre"]'],
    "academias": ['["leisure"="fitness_centre"]'],

    "clínica": ['["amenity"="clinic"]'],
    "clínicas": ['["amenity"="clinic"]'],

    "dentista": ['["amenity"="dentist"]'],
    "dentistas": ['["amenity"="dentist"]'],

    "clínica odontológica": ['["amenity"="dentist"]'],
    "clínicas odontológicas": ['["amenity"="dentist"]'],

    "salão de beleza": ['["shop"="beauty"]'],
    "salões de beleza": ['["shop"="beauty"]'],

    "barbearia": ['["shop"="hairdresser"]'],
    "barbearias": ['["shop"="hairdresser"]'],

    "supermercado": ['["shop"="supermarket"]'],
    "supermercados": ['["shop"="supermarket"]'],

    "padaria": ['["shop"="bakery"]'],
    "padarias": ['["shop"="bakery"]'],

    "pet shop": ['["shop"="pet"]'],
    "pet shops": ['["shop"="pet"]'],

    "imobiliária": ['["office"="estate_agent"]'],
    "imobiliárias": ['["office"="estate_agent"]'],

    "oficina mecânica": ['["shop"="car_repair"]'],
    "oficinas mecânicas": ['["shop"="car_repair"]'],

    "ótica": ['["shop"="optician"]'],
    "óticas": ['["shop"="optician"]']
}


def extrair_termos_consulta(
    query: str
) -> tuple[str, str | None]:

    partes = re.split(
        r"\s+em\s+",
        query,
        maxsplit=1,
        flags=re.IGNORECASE
    )

    if len(partes) == 2:
        categoria = partes[0].strip()
        localizacao = partes[1].strip()

        return categoria, localizacao

    return query.strip(), None


def normalizar_localizacao(localizacao: str) -> str:
    """
    Remove informações estaduais adicionadas ao nome da cidade.

    Exemplo:
    "Piraju - SP" -> "Piraju"
    "Piraju SP" -> "Piraju"
    "Cornélio Procópio - PR" -> "Cornélio Procópio"
    """

    resultado = localizacao.strip()

    # Remove um sufixo de UF (duas letras maiúsculas) com ou sem hífen.
    resultado = re.sub(
        r"\s*-?\s*[A-Z]{2}\s*$",
        "",
        resultado
    )

    return resultado.strip()


def normalizar_categoria(categoria: str) -> list[str]:

    categoria_normalizada = (
        categoria
        .strip()
        .lower()
    )

    if categoria_normalizada in MAPEAMENTO_CATEGORIAS:
        return MAPEAMENTO_CATEGORIAS[
            categoria_normalizada
        ]

    return [
        f'["name"~"{re.escape(categoria)}", i]'
    ]


def construir_query_overpass(
    categoria: str,
    localizacao: str | None
) -> str:

    filtros = normalizar_categoria(
        categoria
    )

    if localizacao:

        localizacao = normalizar_localizacao(
            localizacao
        )

        consultas = []

        for filtro in filtros:

            consultas.append(
                f'nwr{filtro}(area.searchArea);'
            )

        consultas_elementos = "\n".join(
            consultas
        )

        return f"""
[out:json][timeout:30];

area["name"="{localizacao}"]["boundary"="administrative"]->.searchArea;

(
{consultas_elementos}
);

out center tags;
""".strip()

    consultas = []

    for filtro in filtros:

        consultas.append(
            f'nwr{filtro}(-34.0,-74.0,6.0,-28.0);'
        )

    consultas_elementos = "\n".join(
        consultas
    )

    return f"""
[out:json][timeout:30];

(
{consultas_elementos}
);

out center tags;
""".strip()


def obter_localizacao(
    elemento: dict
) -> tuple[float | None, float | None]:

    latitude = elemento.get("lat")
    longitude = elemento.get("lon")

    if latitude is not None and longitude is not None:
        return latitude, longitude

    center = elemento.get(
        "center",
        {}
    )

    return (
        center.get("lat"),
        center.get("lon")
    )


def montar_endereco(tags: dict) -> str:

    partes = []

    rua = tags.get("addr:street")
    numero = tags.get("addr:housenumber")
    bairro = tags.get("addr:suburb")
    cidade = tags.get("addr:city")
    estado = tags.get("addr:state")

    if rua:
        partes.append(rua)

    if numero:
        partes.append(numero)

    if bairro:
        partes.append(bairro)

    if cidade:
        partes.append(cidade)

    if estado:
        partes.append(estado)

    return ", ".join(partes)


def _executar_overpass(overpass_query: str) -> list[dict]:
    """
    Executa uma query Overpass já pronta (com retry entre espelhos,
    e uma segunda rodada completa se todos falharem de primeira) e
    devolve a lista de candidatas já no formato usado pelo resto do
    projeto (nome/endereco/telefone/site).
    """

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }

    response = None
    ultimo_erro = None

    # Duas rodadas pelos 3 espelhos, com uma pausa entre elas. O
    # Overpass público às vezes fica lento em TODOS os espelhos ao
    # mesmo tempo (picos de uso, atualização de base) - uma segunda
    # rodada depois de uma pausa curta resolve a maioria desses casos
    # sem custar caro no orçamento de tempo (300s no Hobby da Vercel).
    for rodada in range(2):

        if rodada > 0:
            print("[overpass] 1ª rodada falhou, tentando de novo...", flush=True)
            time.sleep(3)

        for url in OVERPASS_URLS:

            try:
                print(f"[overpass] tentando espelho: {url}", flush=True)

                response = requests.post(
                    url,
                    data={
                        "data": overpass_query
                    },
                    headers=headers,
                    timeout=15
                )

                response.raise_for_status()
                ultimo_erro = None
                break

            except requests.exceptions.Timeout as error:
                print(f"[overpass] timeout em {url}", flush=True)
                ultimo_erro = error
                continue

            except requests.exceptions.HTTPError as error:
                # 429 (rate limit) e 502/503/504 (servidor ocupado)
                # valem trocar de espelho.
                status = error.response.status_code if error.response else None

                print(
                    f"[overpass] erro HTTP {status} em {url}",
                    flush=True
                )

                if status in (429, 502, 503, 504):
                    ultimo_erro = error

                    if status == 429:
                        time.sleep(1)

                    continue

                raise RuntimeError(
                    f"Erro ao consultar o Overpass API ({url}): {error}"
                )

            except requests.exceptions.RequestException as error:
                print(f"[overpass] falha de rede em {url}: {error}", flush=True)
                ultimo_erro = error
                continue

        if ultimo_erro is None:
            break

    if ultimo_erro is not None:
        raise RuntimeError(
            "Todos os espelhos do Overpass API falharam ou "
            f"estão sobrecarregados, em duas tentativas. "
            f"Último erro: {ultimo_erro}"
        )

    data = response.json()

    resultados = []

    for elemento in data.get("elements", []):

        tags = elemento.get("tags", {})

        resultados.append({
            "nome": tags.get("name", ""),
            "endereco": montar_endereco(tags),
            "telefone": tags.get("phone", ""),
            "site": tags.get("website", "")
        })

    return resultados


# Tags amplas o suficiente pra cobrir a maioria dos pequenos negócios
# locais, sem depender de mapear cada categoria em português pra uma
# tag específica. "shop", "office" e "craft" sozinhos (sem valor
# específico) já casam com centenas de tipos de comércio/serviço.
TAGS_NEGOCIOS_LOCAIS = [
    'nwr["shop"](area.searchArea);',
    'nwr["office"](area.searchArea);',
    'nwr["craft"](area.searchArea);',
    (
        'nwr["amenity"~"^(restaurant|cafe|bar|fast_food|pharmacy|'
        'dentist|clinic|veterinary|driving_school)$"](area.searchArea);'
    ),
    'nwr["leisure"~"^(fitness_centre|sports_centre)$"](area.searchArea);',
    (
        'nwr["tourism"~"^(hotel|hostel|guest_house|apartment)$"]'
        '(area.searchArea);'
    )
]


def construir_query_overpass_ampla(
    cidade: str,
    limite: int = 200
) -> str:
    """
    Monta uma única query que cobre uma variedade ampla de tipos de
    negócio numa cidade, ao invés de uma categoria fixa por vez.
    """

    cidade_normalizada = normalizar_localizacao(cidade)

    consultas_elementos = "\n".join(TAGS_NEGOCIOS_LOCAIS)

    return f"""
[out:json][timeout:25];

area["name"="{cidade_normalizada}"]["boundary"="administrative"]->.searchArea;

(
{consultas_elementos}
);

out center tags {limite};
""".strip()


def buscar_candidatas_amplas(
    cidade: str,
    limite: int = 200
) -> list[dict]:
    """
    Busca candidatas de QUALQUER tipo de negócio numa cidade, numa
    única chamada ao Overpass - sem categoria fixa.
    """

    if not cidade or not cidade.strip():
        raise ValueError(
            "A cidade não pode estar vazia."
        )

    overpass_query = construir_query_overpass_ampla(
        cidade,
        limite=limite
    )

    resultados = _executar_overpass(overpass_query)

    # Descarta candidatas sem nome (não dá pra verificar nem salvar).
    return [
        r for r in resultados
        if r.get("nome", "").strip()
    ]


def pesquisar_web(
    query: str,
    quantidade: int = 10
) -> dict:

    if not query.strip():
        raise ValueError(
            "A consulta de pesquisa não pode estar vazia."
        )

    quantidade = max(
        1,
        min(
            20,
            quantidade
        )
    )

    categoria, localizacao = extrair_termos_consulta(query)

    overpass_query = construir_query_overpass(
        categoria,
        localizacao
    )

    resultados = _executar_overpass(overpass_query)
    resultados = resultados[:quantidade]

    return {
        "consulta": query,
        "quantidade_resultados": len(resultados),
        "resultados": resultados
    }


pesquisar_web_tool = {
    "name": "pesquisar_web",
    "description": (
        "Pesquisa empresas e estabelecimentos utilizando "
        "dados públicos do OpenStreetMap através do Overpass API. "
        "Use essa ferramenta para descobrir empresas por "
        "segmento, cidade ou região. "
        "Os resultados retornados devem ser analisados antes "
        "de realizar novas pesquisas.\n\n"
        "IMPORTANTE - FORMATO OBRIGATÓRIO DA QUERY:\n"
        "Cada chamada deve conter exatamente UM segmento e, quando "
        "aplicável, UMA localização, no formato "
        "'<segmento> em <cidade>' ou '<segmento> em <cidade> <UF>'. "
        "NÃO combine múltiplos segmentos na mesma consulta. "
        "NÃO combine múltiplas cidades ou regiões na mesma consulta. "
        "NÃO inclua texto extra como 'empresas de pequeno ou médio "
        "porte' dentro da query - isso não é um segmento válido e "
        "impede a busca de retornar resultados.\n\n"
        "Exemplos CORRETOS:\n"
        "- 'clínicas em Cornélio Procópio PR'\n"
        "- 'barbearias em Cornélio Procópio'\n"
        "- 'hotéis em Piraju SP'\n\n"
        "Exemplos INCORRETOS (não use):\n"
        "- 'empresas pequeno porte clínicas barbearias hotéis em "
        "Cornélio Procópio e Piraju'\n"
        "- 'clínicas e barbearias em Cornélio Procópio'\n\n"
        "Para cobrir vários segmentos e várias localizações, faça "
        "uma chamada separada para cada combinação de segmento e "
        "localização."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Consulta contendo APENAS UM segmento e, quando "
                    "necessário, UMA cidade ou região, separados pela "
                    "palavra ' em '. "
                    "Exemplo: "
                    "'clínicas odontológicas em Cornélio Procópio PR'."
                )
            },
            "quantidade": {
                "type": "integer",
                "description": (
                    "Quantidade máxima de resultados desejados. "
                    "Prefira valores entre 5 e 10."
                ),
                "minimum": 1,
                "maximum": 20,
                "default": 10
            }
        },
        "required": [
            "query"
        ]
    }
}


if __name__ == "__main__":

    resultado = pesquisar_web(
        "clínicas odontológicas em Cornélio Procópio PR",
        quantidade=5
    )

    print(
        f"\nConsulta: {resultado['consulta']}"
    )

    print(
        f"Resultados encontrados: "
        f"{resultado['quantidade_resultados']}\n"
    )

    for empresa in resultado["resultados"]:

        print(
            empresa
        )