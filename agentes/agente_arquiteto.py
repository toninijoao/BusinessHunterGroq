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
    caminho = base_dir / "prompts" / "arquiteto.md"

    return caminho.read_text(encoding="utf-8")


def carregar_schema() -> dict:
    caminho = base_dir / "schemas" / "solucao.json"

    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def executar_arquiteto(perfil: dict) -> dict:

    system_prompt = carregar_prompt()
    schema = carregar_schema()

    tarefa = f"""
Analise o perfil de negocio abaixo e determine a solucao digital
mais adequada para essa empresa.

PERFIL DO NEGOCIO:
{json.dumps(perfil, ensure_ascii=False, indent=2)}
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
                "name": "solucao_digital",
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
            "O agente arquiteto nao retornou nenhum resultado."
        )

    return json.loads(conteudo)
