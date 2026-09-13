import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


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


def carregar_prompt() -> str:
    caminho = base_dir / "prompts" / "planilha.md"

    return caminho.read_text(encoding="utf-8")


def carregar_schema() -> dict:
    caminho = base_dir / "schemas" / "planilha.json"

    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def executar_planilha(
    empresa: dict,
    perfil: dict,
    solucao: dict
) -> dict:

    system_prompt = carregar_prompt()
    schema = carregar_schema()

    tarefa = f"""
Organize os dados abaixo para a planilha.

DADOS DA EMPRESA:
{json.dumps(empresa, ensure_ascii=False, indent=2)}

PERFIL DO NEGOCIO:
{json.dumps(perfil, ensure_ascii=False, indent=2)}

SOLUCAO RECOMENDADA:
{json.dumps(solucao, ensure_ascii=False, indent=2)}
"""

    response = obter_client().chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": tarefa
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "planilha",
                "strict": True,
                "schema": schema
            }
        }
    )

    return extrair_resultado(response)


def extrair_resultado(response) -> dict:

    conteudo = response.choices[0].message.content

    if not conteudo:
        raise ValueError(
            "O agente planilha nao retornou nenhum resultado."
        )

    try:
        return json.loads(conteudo)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"O agente planilha retornou um JSON invalido: {error}"
        )
