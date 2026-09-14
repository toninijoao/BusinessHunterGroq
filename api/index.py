import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orquestrador.orquestrador import carregar_config
from orquestrador.candidatos import listar_candidatas, processar_candidata
from agentes.agente_filtro import executar_filtro
from agentes.agente_arquiteto import executar_arquiteto
from agentes.agente_planilha import executar_planilha


app = FastAPI(title="Business Hunter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config_publica():
    """
    Expõe a quantidade-alvo de empresas configurada, pra o frontend
    saber quando parar de processar candidatas.
    """

    config = carregar_config()

    return {
        "quantidade_empresas": config.get("quantidade_empresas", 8)
    }


class ProcessarCandidataRequest(BaseModel):
    candidata: dict
    cidade: str
    estado: str = ""


@app.get("/api/candidatas")
def candidatas(cidade: str, estado: str = ""):
    """
    Lista candidatas de QUALQUER tipo de negócio em UMA cidade,
    direto via Overpass (sem LLM, sem categoria fixa). Uma única
    chamada por cidade.
    """

    try:
        lista = listar_candidatas(cidade=cidade)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    return {"candidatas": lista}


@app.post("/api/processar_candidata")
def processar(payload: ProcessarCandidataRequest):
    """
    Processa UMA candidata: verifica se já existe, verifica se tem
    site (decisão determinística, sem LLM) e, se aceita, gera
    perfil/solução/planilha (essas três etapas usam LLM) e salva.
    Pensado pra ser chamado uma vez por candidata, permitindo ao
    frontend mostrar cada empresa assim que ela é aceita.
    """

    try:
        resultado = processar_candidata(
            payload.candidata,
            cidade=payload.cidade,
            estado=payload.estado
        )

        if not resultado.get("aceita"):
            return resultado

        empresa = resultado["empresa"]

        try:
            perfil = executar_filtro(empresa)
            solucao = executar_arquiteto(perfil)
            dados_planilha = executar_planilha(empresa, perfil, solucao)

            resultado["perfil"] = perfil
            resultado["solucao"] = solucao
            resultado["planilha"] = dados_planilha

        except Exception as error:
            resultado["erro_enriquecimento"] = str(error)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    return resultado


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
