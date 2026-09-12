import re
from urllib.parse import urlparse

import requests
from ddgs import DDGS


DOMINIOS_IGNORADOS = {
    "instagram.com",
    "facebook.com",
    "linkedin.com",
    "google.com",
    "google.com.br",
    "maps.google.com",
    "tripadvisor.com",
    "yelp.com",
    "ifood.com.br",
    "cnpj.biz",
}


def normalizar_texto(texto: str) -> str:
    texto = texto.lower()

    texto = re.sub(
        r"[^a-z0-9áàâãéêíóôõúçü\s]",
        " ",
        texto
    )

    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def extrair_dominio(url: str) -> str:
    dominio = urlparse(url).netloc.lower()

    if dominio.startswith("www."):
        dominio = dominio[4:]

    return dominio


def dominio_ignorado(url: str) -> bool:
    dominio = extrair_dominio(url)

    return any(
        dominio == ignorado
        or dominio.endswith(f".{ignorado}")
        for ignorado in DOMINIOS_IGNORADOS
    )


def dominio_compativel(
    url: str,
    nome_empresa: str
) -> bool:

    dominio = extrair_dominio(url)

    nome_normalizado = normalizar_texto(nome_empresa)

    palavras = [
        palavra
        for palavra in nome_normalizado.split()
        if len(palavra) >= 3
    ]

    if not palavras:
        return False

    dominio_limpo = re.sub(
        r"[^a-z0-9]",
        "",
        dominio
    )

    correspondencias = sum(
        1
        for palavra in palavras
        if palavra in dominio_limpo
    )

    return correspondencias >= 1


def verificar_conteudo_site(
    url: str,
    nome_empresa: str
) -> bool:

    try:
        resposta = requests.get(
            url,
            timeout=10,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        if resposta.status_code >= 400:
            return False

        conteudo = resposta.text[:500000].lower()

        nome_normalizado = normalizar_texto(
            nome_empresa
        )

        palavras = [
            palavra
            for palavra in nome_normalizado.split()
            if len(palavra) >= 3
        ]

        if not palavras:
            return False

        titulo_match = False
        texto_match = False

        titulo = re.search(
            r"<title[^>]*>(.*?)</title>",
            conteudo,
            re.DOTALL
        )

        if titulo:
            titulo_texto = normalizar_texto(
                titulo.group(1)
            )

            titulo_match = all(
                palavra in titulo_texto
                for palavra in palavras
            )

        texto_limpo = re.sub(
            r"<[^>]+>",
            " ",
            conteudo
        )

        texto_limpo = normalizar_texto(
            texto_limpo
        )

        texto_match = all(
            palavra in texto_limpo
            for palavra in palavras
        )

        return titulo_match or texto_match

    except requests.RequestException:
        return False


def verificar_site(
    nome_empresa: str,
    cidade: str,
    site_encontrado: str | None = None
) -> dict:

    if not nome_empresa.strip():
        raise ValueError(
            "O nome da empresa não pode estar vazio."
        )

    if not cidade.strip():
        raise ValueError(
            "A cidade da empresa não pode estar vazia."
        )

    if site_encontrado:

        if not dominio_ignorado(site_encontrado):

            if verificar_conteudo_site(
                site_encontrado,
                nome_empresa
            ):
                return {
                    "status": "WEBSITE_FOUND",
                    "website": site_encontrado,
                    "confidence": 0.98,
                    "evidence": [
                        "O Google Places forneceu um website.",
                        "O domínio não pertence a uma plataforma externa.",
                        "O conteúdo do site apresenta correspondência com o nome da empresa."
                    ]
                }

    consultas = [
        f'"{nome_empresa}" "{cidade}"',
        f'"{nome_empresa}" site'
    ]

    resultados = []

    try:

        with DDGS() as ddgs:

            for consulta in consultas:

                encontrados = ddgs.text(
                    consulta,
                    region="br-pt",
                    safesearch="off",
                    max_results=5
                )

                for resultado in encontrados:

                    resultados.append(
                        {
                            "consulta": consulta,
                            "titulo": resultado.get("title"),
                            "url": resultado.get("href")
                        }
                    )

    except Exception as error:

        raise RuntimeError(
            f"Erro ao pesquisar possíveis sites: {error}"
        )

    urls = set()
    resultados_unicos = []

    for resultado in resultados:

        url = resultado["url"]

        if not url:
            continue

        if url in urls:
            continue

        urls.add(url)

        resultados_unicos.append(
            resultado
        )

    possiveis_sites = []

    for resultado in resultados_unicos:

        url = resultado["url"]

        if dominio_ignorado(url):
            continue

        if not dominio_compativel(
            url,
            nome_empresa
        ):
            continue

        if not verificar_conteudo_site(
            url,
            nome_empresa
        ):
            continue

        possiveis_sites.append(
            {
                "url": url,
                "titulo": resultado["titulo"]
            }
        )

    if possiveis_sites:

        return {
            "status": "WEBSITE_FOUND",
            "website": possiveis_sites[0]["url"],
            "confidence": 0.90,
            "evidence": possiveis_sites[:5]
        }

    if resultados_unicos:

        # Houve resultados nas buscas, mas nenhum passou nos filtros
        # de domínio ignorado / domínio compatível / conteúdo
        # correspondente. Isso é evidência razoável de que não existe
        # um site oficial funcional dessa empresa.
        return {
            "status": "WEBSITE_NOT_FOUND",
            "website": None,
            "confidence": 0.75,
            "evidence": resultados_unicos[:10]
        }

    # Nenhum resultado em nenhuma das consultas realizadas.
    # Evidência mais fraca (não sabemos se a busca falhou por
    # falta de indexação ou porque a empresa realmente não tem site),
    # então fica como incerto em vez de confirmar ausência.
    return {
        "status": "WEBSITE_UNCERTAIN",
        "website": None,
        "confidence": 0.30,
        "evidence": []
    }


verificar_site_tool = {
    "name": "verificar_site",
    "description": (
        "Verifica se uma empresa possui um site oficial funcional. "
        "Analisa sites encontrados no Google Places ou em pesquisas "
        "na web e rejeita redes sociais, diretórios e outras "
        "plataformas externas."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nome_empresa": {
                "type": "string",
                "description": "Nome da empresa."
            },
            "cidade": {
                "type": "string",
                "description": "Cidade da empresa."
            },
            "site_encontrado": {
                "type": "string",
                "description": (
                    "Website fornecido pelo Google Places, "
                    "caso exista."
                )
            }
        },
        "required": [
            "nome_empresa",
            "cidade"
        ]
    }
}


if __name__ == "__main__":

    resultado = verificar_site(
        nome_empresa="Empresa Exemplo",
        cidade="Cornélio Procópio",
        site_encontrado=None
    )

    print(resultado)