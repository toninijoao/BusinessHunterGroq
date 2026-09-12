from tools.pesquisa_web import pesquisar_web, pesquisar_web_tool
from tools.checkagem_site import verificar_site, verificar_site_tool
from tools.mapeador import mapear_endereco, mapear_endereco_tool
from tools.database import (
    buscar_empresa,
    buscar_empresa_tool,
    salvar_empresa,
    salvar_empresa_tool
)


tool_functions = {
    "pesquisar_web": pesquisar_web,
    "verificar_site": verificar_site,
    "mapear_endereco": mapear_endereco,
    "buscar_empresa": buscar_empresa,
    "salvar_empresa": salvar_empresa
}


def formato_openai(tool_dict: dict) -> dict:
    """
    Converte um schema de tool no formato usado internamente
    (name/description/input_schema) para o formato que a API
    da Groq (compativel com OpenAI) espera.
    """

    return {
        "type": "function",
        "function": {
            "name": tool_dict["name"],
            "description": tool_dict["description"],
            "parameters": tool_dict["input_schema"]
        }
    }


tools = [
    formato_openai(pesquisar_web_tool),
    formato_openai(verificar_site_tool),
    formato_openai(mapear_endereco_tool),
    formato_openai(buscar_empresa_tool),
    formato_openai(salvar_empresa_tool)
]