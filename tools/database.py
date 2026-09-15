import os

from dotenv import load_dotenv
from supabase import create_client, Client


load_dotenv()

_supabase: Client | None = None

CAMPOS_TABELA = [
    "name",
    "city",
    "state",
    "country",
    "address",
    "phone",
    "instagram",
    "facebook",
    "google_maps",
    "website",
    "website_status",
    "website_confidence"
]


def obter_supabase() -> Client:
    """
    Cria o cliente do Supabase só na primeira vez que for usado.
    Se SUPABASE_URL/SUPABASE_KEY tiverem algum problema, isso só
    quebra quem realmente precisa do banco, e não a importação do
    módulo inteiro (o que derrubaria rotas que nem usam banco de
    dados, como /api/config e /api/health).
    """

    global _supabase

    if _supabase is None:

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")

        if not supabase_url:
            raise ValueError(
                "SUPABASE_URL não encontrada nas variáveis de ambiente."
            )

        if not supabase_key:
            raise ValueError(
                "SUPABASE_KEY não encontrada nas variáveis de ambiente."
            )

        _supabase = create_client(
            supabase_url,
            supabase_key
        )

    return _supabase


def buscar_empresa(
    nome: str,
    cidade: str | None = None,
    telefone: str | None = None
) -> dict:

    query = (
        obter_supabase()
        .table("companies")
        .select("*")
        .ilike("name", nome)
    )

    if cidade:
        query = query.ilike("city", cidade)

    if telefone:
        query = query.eq("phone", telefone)

    response = query.execute()

    empresas = response.data or []

    return {
        "encontrada": len(empresas) > 0,
        "quantidade": len(empresas),
        "empresas": empresas
    }


def listar_empresas_por_cidade(cidade: str) -> list[dict]:
    """
    Lista todas as empresas já salvas de uma cidade (de buscas
    anteriores), só com os campos que existem na tabela.
    """

    response = (
        obter_supabase()
        .table("companies")
        .select(",".join(CAMPOS_TABELA))
        .ilike("city", cidade)
        .execute()
    )

    return response.data or []


def salvar_empresa(empresa: dict) -> dict:

    dados = {
        campo: empresa.get(campo)
        for campo in CAMPOS_TABELA
    }

    dados["country"] = empresa.get("country", "Brasil")

    response = (
        obter_supabase()
        .table("companies")
        .insert(dados)
        .execute()
    )

    return {
        "sucesso": True,
        "empresa": (
            response.data[0]
            if response.data
            else None
        )
    }


buscar_empresa_tool = {
    "name": "buscar_empresa",
    "description": (
        "Consulta o banco de dados para verificar se uma empresa "
        "já foi registrada. Use antes de salvar uma nova empresa "
        "para evitar duplicatas."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "nome": {
                "type": "string",
                "description": "Nome da empresa."
            },
            "cidade": {
                "type": "string",
                "description": "Cidade da empresa."
            },
            "telefone": {
                "type": "string",
                "description": "Telefone da empresa, caso disponível."
            }
        },
        "required": [
            "nome"
        ]
    }
}


salvar_empresa_tool = {
    "name": "salvar_empresa",
    "description": (
        "Salva uma empresa validada no banco de dados. "
        "Use somente depois de confirmar que a empresa é válida "
        "e não está duplicada. "
        "Os campos de 'empresa' seguem exatamente o mesmo formato "
        "do schema de resposta final (schemas/empresa.json): "
        "chaves em inglês."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "empresa": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string"
                    },
                    "city": {
                        "type": "string"
                    },
                    "state": {
                        "type": "string"
                    },
                    "country": {
                        "type": "string"
                    },
                    "address": {
                        "type": "string"
                    },
                    "phone": {
                        "type": "string"
                    },
                    "instagram": {
                        "type": "string"
                    },
                    "facebook": {
                        "type": "string"
                    },
                    "google_maps": {
                        "type": "string"
                    },
                    "website": {
                        "type": "string"
                    },
                    "website_status": {
                        "type": "string"
                    },
                    "website_confidence": {
                        "type": "number"
                    }
                },
                "required": [
                    "name",
                    "city",
                    "state",
                    "country"
                ]
            }
        },
        "required": [
            "empresa"
        ]
    }
}


if __name__ == "__main__":

    resultado = buscar_empresa(
        nome="Empresa Exemplo",
        cidade="Cornélio Procópio"
    )

    print(resultado)
