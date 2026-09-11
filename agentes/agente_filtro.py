import json
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from tools.pesquisa_web import pesquisar_web, pesquisar_web_tool
from tools.mapeador import mapear_endereco, mapear_endereco_tool
from tools.registro import formato_openai


load_dotenv()

client = Groq()
model = "openai/gpt-oss-120b"

base_dir = Path(__file__).resolve().parent.parent


def carregar_prompt() -> str:
    caminho = base_dir / "prompts" / "perfil.md"

    return caminho.read_text(encoding="utf-8")


def carregar_schema() -> dict:
    caminho = base_dir / "schemas" / "perfil.json"

    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


tools = [
    formato_openai(pesquisar_web_tool),
    formato_openai(mapear_endereco_tool)
]


tool_functions = {
    "pesquisar_web": pesquisar_web,
    "mapear_endereco": mapear_endereco
}


def executar_tool(nome: str, argumentos: dict):
    if nome not in tool_functions:
        raise ValueError(
            f"Ferramenta desconhecida: {nome}"
        )

    return tool_functions[nome](**argumentos)


def executar_filtro(empresa: dict) -> dict:

    system_prompt = carregar_prompt()
    schema = carregar_schema()

    tarefa = f"""
Construa o perfil de negocio da empresa abaixo.

Empresa:
{json.dumps(empresa, ensure_ascii=False, indent=2)}
"""

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

    max_iteracoes = 15
    iteracao = 0

    while True:

        iteracao += 1

        if iteracao > max_iteracoes:
            raise RuntimeError(
                "O agente filtro atingiu o limite maximo de "
                "iteracoes sem concluir a tarefa."
            )

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools
        )

        mensagem = response.choices[0].message

        messages.append(mensagem.model_dump(exclude_none=True))

        if not mensagem.tool_calls:
            break

        for tool_call in mensagem.tool_calls:

            try:
                argumentos = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                argumentos = {}

            try:
                resultado = executar_tool(
                    tool_call.function.name,
                    argumentos
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

    mensagens_finais = messages + [
        {
            "role": "user",
            "content": (
                "Finalize agora. Retorne exclusivamente um objeto "
                "JSON compativel com o schema fornecido, com o "
                "perfil de negocio dessa empresa."
            )
        }
    ]

    resposta_final = client.chat.completions.create(
        model=model,
        messages=mensagens_finais,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "perfil_negocio",
                "strict": True,
                "schema": schema
            }
        }
    )

    return extrair_resultado(resposta_final)


def extrair_resultado(response) -> dict:

    conteudo = response.choices[0].message.content

    if not conteudo:
        raise ValueError(
            "O agente filtro nao retornou nenhum resultado."
        )

    try:
        return json.loads(conteudo)

    except json.JSONDecodeError as error:
        raise ValueError(
            f"O agente filtro retornou um JSON invalido: {error}"
        )
