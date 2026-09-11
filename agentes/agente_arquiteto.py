import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

client = Groq()
model = "openai/gpt-oss-120b"

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

    response = client.chat.completions.create(
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
