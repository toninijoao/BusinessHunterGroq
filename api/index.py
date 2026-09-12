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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/executar")
def executar(payload: ExecutarRequest):
    """
    Roda o pipeline completo (Hunter -> Filtro -> Arquiteto -> Planilha)
    para a cidade escolhida pelo usuário e retorna o resultado.
    Pode demorar até alguns minutos dependendo da quantidade de
    empresas configurada em config/config.yaml.
    """

    try:
        config = carregar_config()

        tarefa = criar_tarefa(
            config,
            cidade=payload.cidade,
            estado=payload.estado
        )

        resultado = executar_pipeline(
            tarefa,
            segmentos=config.get("segmentos"),
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
