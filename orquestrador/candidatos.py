from urllib.parse import quote

from tools.pesquisa_web import buscar_candidatas_amplas
from tools.checkagem_site import verificar_site
from tools.database import buscar_empresa, salvar_empresa


def listar_candidatas(cidade: str) -> list[dict]:
    """
    Busca candidatas de QUALQUER tipo de negócio numa cidade,
    direto via Overpass (sem nenhuma chamada a LLM, sem categoria
    fixa - rápido e determinístico).
    """

    return buscar_candidatas_amplas(cidade)


def _montar_link_maps(nome: str, cidade: str, estado: str) -> str:

    consulta = f"{nome}, {cidade}"

    if estado:
        consulta += f" - {estado}"

    return (
        "https://www.google.com/maps/search/?api=1&query="
        f"{quote(consulta)}"
    )


def processar_candidata(
    candidata: dict,
    cidade: str,
    estado: str
) -> dict:
    """
    Decide deterministicamente se uma candidata deve ser aceita:
    - Ja cadastrada -> rejeitada.
    - Tem site (WEBSITE_FOUND) ou evidencia insuficiente
      (WEBSITE_UNCERTAIN) -> rejeitada.
    - Sem site confirmado (WEBSITE_NOT_FOUND) -> aceita e salva.

    Nao usa nenhuma chamada a LLM - so entra IA depois, para gerar
    o perfil/solucao/planilha de uma candidata ja aceita.
    """

    nome = (candidata.get("nome") or "").strip()

    if not nome:
        return {
            "aceita": False,
            "motivo": "candidata sem nome"
        }

    duplicada = buscar_empresa(
        nome=nome,
        cidade=cidade,
        telefone=candidata.get("telefone") or ""
    )

    if duplicada.get("encontrada"):
        return {
            "aceita": False,
            "nome": nome,
            "motivo": "empresa ja cadastrada"
        }

    verificacao = verificar_site(
        nome_empresa=nome,
        cidade=cidade,
        site_encontrado=candidata.get("site") or None
    )

    if verificacao["status"] != "WEBSITE_NOT_FOUND":
        return {
            "aceita": False,
            "nome": nome,
            "motivo": verificacao["status"]
        }

    fontes = []

    for item in verificacao.get("evidence", []):
        url = item.get("url") if isinstance(item, dict) else None
        if url and url not in fontes:
            fontes.append(url)

    empresa = {
        "name": nome,
        "city": cidade,
        "state": estado,
        "country": "Brasil",
        "address": candidata.get("endereco") or "",
        "phone": candidata.get("telefone") or "",
        "instagram": "",
        "facebook": "",
        "google_maps": _montar_link_maps(nome, cidade, estado),
        "website": "",
        "website_status": verificacao["status"],
        "website_confidence": verificacao.get("confidence", 0),
        "sources": fontes
    }

    salvar_empresa(empresa)

    return {
        "aceita": True,
        "empresa": empresa
    }
