import sys
from pathlib import Path

# Garante que os módulos do projeto (agentes, tools, orquestrador...)
# sejam importáveis tanto na Vercel quanto rodando localmente.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orquestrador.orquestrador import (
    carregar_config,
    criar_tarefa,
    executar_pipeline
)
from orquestrador.candidatos import listar_candidatas, processar_candidata
from agentes.agente_filtro import executar_filtro
from agentes.agente_arquiteto import executar_arquiteto
from agentes.agente_planilha import executar_planilha


app = FastAPI(title="Business Hunter API")

# Em produção (Vercel), frontend e API ficam no mesmo domínio, então
# CORS nem seria necessário. Deixamos liberado mesmo assim porque não
# custa nada e ajuda em cenários de desenvolvimento fora do padrão.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)


class ExecutarRequest(BaseModel):
    cidade: str
    estado: str = ""
    segmento: str | None = None


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/config")
def config_publica():
    """
    Expõe a lista de segmentos e a quantidade configurada, pra o
    frontend saber por quais segmentos iterar sem duplicar essa
    lista no código do TypeScript.
    """

    config = carregar_config()

    return {
        "segmentos": config.get("segmentos", []),
        "quantidade_empresas": config.get("quantidade_empresas", 20)
    }


class ProcessarCandidataRequest(BaseModel):
    candidata: dict
    cidade: str
    estado: str = ""


@app.get("/api/candidatas")
def candidatas(cidade: str, segmento: str, estado: str = ""):
    """
    Lista candidatas de UM segmento em UMA cidade, direto via
    Overpass (sem LLM). Rápido e barato — pensado pra ser chamado
    uma vez por segmento a partir do frontend.
    """

    try:
        lista = listar_candidatas(
            cidade=cidade,
            estado=estado,
            segmento=segmento
        )

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
            # A empresa já foi aceita e salva - só o enriquecimento
            # (perfil/solução/planilha) falhou. Devolve a empresa
            # mesmo assim, com o erro anotado.
            resultado["erro_enriquecimento"] = str(error)

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )

    return resultado


@app.post("/api/executar")
def executar(payload: ExecutarRequest):
    """
    Roda o pipeline (Hunter -> Filtro -> Arquiteto -> Planilha) para a
    cidade escolhida. Se 'segmento' for informado, pesquisa somente
    esse segmento (chamada rápida, pensada pra ser feita uma vez por
    segmento a partir do frontend, evitando estourar o limite de
    tempo de uma função serverless). Se omitido, roda todos os
    segmentos configurados numa única chamada (uso local/CLI, sem
    limite de tempo).
    """

    try:
        config = carregar_config()

        tarefa = criar_tarefa(
            config,
            cidade=payload.cidade,
            estado=payload.estado,
            segmento=payload.segmento
        )

        segmentos_para_rodar = (
            [payload.segmento]
            if payload.segmento
            else config.get("segmentos")
        )

        resultado = executar_pipeline(
            tarefa,
            segmentos=segmentos_para_rodar,
            cidade=payload.cidade
        )

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
