import json
import re
import unicodedata
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from tools.registro import tools, tool_functions


load_dotenv()

_client: Groq | None = None
model = "openai/gpt-oss-120b"


def obter_client() -> Groq:
    """
    Cria o cliente da Groq só na primeira vez que for usado.
    Se a chave GROQ_API_KEY tiver algum problema, isso só
    quebra quem realmente chama a Groq, e não a importação
    do módulo inteiro (o que derrubaria rotas que nem usam IA).
    """
    global _client

    if _client is None:
        _client = Groq()

    return _client

base_dir = Path(__file__).resolve().parent.parent

STOPWORDS_SEGMENTO = {"de", "do", "da", "e", "estilo", "empresas"}


def carregar_prompt() -> str:
    caminho = base_dir / "prompts" / "descoberta.md"

    return caminho.read_text(encoding="utf-8")


def carregar_schema() -> dict:
    caminho = base_dir / "schemas" / "empresa.json"

    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def normalizar_texto(texto: str) -> str:

    texto = unicodedata.normalize("NFKD", texto or "")
    texto = texto.encode("ascii", "ignore").decode("ascii")

    return texto.lower()


def representante_segmento(segmento: str) -> str:
    """
    Reduz um segmento configurado (ex: 'estadias(estilo airbnb)',
    'empresas de servico') a uma palavra-chave representativa
    ('estadias', 'servico'), pra dar pra checar se ele ja foi
    pesquisado, sem depender do texto exato que o modelo usar.
    """

    texto = normalizar_texto(segmento)
    palavras = re.findall(r"[a-z0-9]+", texto)
    palavras = [p for p in palavras if p not in STOPWORDS_SEGMENTO]

    return palavras[0] if palavras else texto


def executar_tool(nome: str, argumentos: dict):

    if nome not in tool_functions:
        raise ValueError(
            f"Ferramenta desconhecida: {nome}"
        )

    funcao = tool_functions[nome]

    return funcao(**argumentos)


def executar_hunter(
    tarefa: str,
    segmentos: list | None = None,
    cidade: str | None = None
) -> dict:

    debug_log: list[str] = []

    def registrar(*partes: object) -> None:
        linha = " ".join(str(p) for p in partes)
        print(linha, flush=True)
        debug_log.append(linha)

    try:
        resultado = _executar_hunter_interno(
            tarefa,
            segmentos,
            cidade,
            registrar
        )
        resultado["debug_log"] = debug_log
        return resultado

    except Exception as error:

        registrar("ERRO FATAL NO HUNTER:", f"{type(error).__name__}: {error}")

        return {
            "empresas": [],
            "erro": f"{type(error).__name__}: {error}",
            "debug_log": debug_log
        }


def _executar_hunter_interno(
    tarefa: str,
    segmentos: list | None,
    cidade: str | None,
    registrar
) -> dict:

    system_prompt = carregar_prompt()
    cidade_ref = cidade or "na cidade informada"

    messages = [
        {
            "role": "system",
            "content": system_prompt
        },
        {
            "role": "user",
            "content": tarefa
        }
    ]

    segmentos_pendentes = {
        representante_segmento(segmento): segmento
        for segmento in (segmentos or [])
    }
    segmentos_consultados = set()

    max_iteracoes = 40
    iteracao = 0
    avisos_continuar = 0
    max_avisos_continuar = len(segmentos_pendentes) + 2

    while True:

        iteracao += 1

        if iteracao > max_iteracoes:
            raise RuntimeError(
                "O Hunter atingiu o limite maximo de iteracoes "
                "sem concluir a tarefa."
            )

        registrar(f"--- Chamando Groq (iteracao {iteracao}) ---")

        response = obter_client().chat.completions.create(
            model=model,
            messages=messages,
            tools=tools
        )

        mensagem = response.choices[0].message

        messages.append(mensagem.model_dump(exclude_none=True))

        registrar(f"ITERACAO {iteracao}")
        registrar("TOOL_CALLS:", mensagem.tool_calls)
        registrar("CONTENT (resposta do modelo):", mensagem.content)

        if mensagem.tool_calls:

            for tool_call in mensagem.tool_calls:

                nome_tool = tool_call.function.name

                try:
                    argumentos = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    argumentos = {}

                registrar("TOOL CHAMADA:", nome_tool, "| Argumentos:", argumentos)

                if nome_tool == "pesquisar_web":

                    consulta_normalizada = normalizar_texto(
                        argumentos.get("query", "")
                    )

                    for chave in list(segmentos_pendentes.keys()):
                        if chave in consulta_normalizada:
                            segmentos_consultados.add(chave)

                try:

                    resultado = executar_tool(
                        nome_tool,
                        argumentos
                    )

                    registrar(
                        "RESULTADO DA TOOL:",
                        json.dumps(resultado, ensure_ascii=False)
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(
                                resultado,
                                ensure_ascii=False
                            )
                        }
                    )

                except Exception as error:

                    registrar("ERRO NA TOOL:", str(error))

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(
                                {
                                    "error": str(error)
                                },
                                ensure_ascii=False
                            )
                        }
                    )

            continue

        # O modelo respondeu sem chamar nenhuma ferramenta.
        # So aceita isso como "terminei" se ja tiver ao menos
        # tentado pesquisar todos os segmentos configurados.
        faltando = {
            chave: nome
            for chave, nome in segmentos_pendentes.items()
            if chave not in segmentos_consultados
        }

        if faltando and avisos_continuar < max_avisos_continuar:

            avisos_continuar += 1

            lista_faltando = ", ".join(faltando.values())

            registrar(
                "Modelo tentou parar sem cobrir todos os segmentos. "
                f"Faltando: {lista_faltando}"
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "Voce ainda nao chamou pesquisar_web para os "
                        f"seguintes segmentos: {lista_faltando}. "
                        "Continue agora mesmo chamando pesquisar_web "
                        f"para o proximo desses segmentos em {cidade_ref}, "
                        "no formato '<segmento> em <cidade>'. "
                        "Nao finalize antes de tentar todos."
                    )
                }
            )

            continue

        break

    schema = carregar_schema()

    mensagens_finais = messages + [
        {
            "role": "user",
            "content": (
                "Finalize a tarefa agora. "
                "Retorne exclusivamente um objeto JSON "
                "compativel com o schema fornecido. "
                "Inclua somente empresas reais e efetivamente "
                "validadas pelas ferramentas. "
                "Nao invente nenhum dado. "
                "Empresas rejeitadas nao devem aparecer. "
                "Se nenhuma empresa valida tiver sido encontrada, "
                "retorne {\"empresas\": []}."
            )
        }
    ]

    registrar("--- Chamando Groq para o JSON final ---")

    resposta_final = obter_client().chat.completions.create(
        model=model,
        messages=mensagens_finais,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "empresas_encontradas",
                "strict": True,
                "schema": schema
            }
        }
    )

    resultado = extrair_resultado(resposta_final)

    registrar(
        "RESULTADO FINAL:",
        json.dumps(resultado, ensure_ascii=False)
    )

    return resultado


def extrair_resultado(response) -> dict:

    conteudo = response.choices[0].message.content

    if not conteudo:
        raise ValueError(
            "O Hunter nao retornou nenhum resultado."
        )

    try:

        resultado = json.loads(conteudo)

    except json.JSONDecodeError as error:

        raise ValueError(
            f"O Hunter retornou um JSON invalido: {error}"
        )

    if not isinstance(resultado, dict):

        raise ValueError(
            "O resultado do Hunter deve ser um objeto JSON."
        )

    if "empresas" not in resultado:

        raise ValueError(
            "O resultado do Hunter nao possui o campo 'empresas'."
        )

    if not isinstance(resultado["empresas"], list):

        raise ValueError(
            "O campo 'empresas' deve ser uma lista."
        )

    return resultado
