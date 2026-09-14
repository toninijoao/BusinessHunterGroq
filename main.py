from orquestrador.orquestrador import carregar_config
from orquestrador.candidatos import listar_candidatas, processar_candidata
from agentes.agente_filtro import executar_filtro
from agentes.agente_arquiteto import executar_arquiteto
from agentes.agente_planilha import executar_planilha


def main():
    config = carregar_config()
    alvo = config.get("quantidade_empresas", 8)

    cidade = input("Cidade: ").strip()
    estado = input("Estado (UF, opcional): ").strip()

    print(f"\nBuscando candidatas em {cidade}...")
    candidatas = listar_candidatas(cidade)
    print(f"{len(candidatas)} candidata(s) encontrada(s) no total.\n")

    aceitas = 0

    for candidata in candidatas:

        if aceitas >= alvo:
            print(f"\nMeta de {alvo} empresas atingida, parando.")
            break

        print(f"Verificando: {candidata.get('nome')}...")
        resultado = processar_candidata(candidata, cidade=cidade, estado=estado)

        if not resultado.get("aceita"):
            print(f"  -> rejeitada ({resultado.get('motivo')})")
            continue

        aceitas += 1
        empresa = resultado["empresa"]
        print(f"  -> ACEITA ({aceitas}/{alvo}): {empresa['name']}")

        try:
            perfil = executar_filtro(empresa)
            solucao = executar_arquiteto(perfil)
            executar_planilha(empresa, perfil, solucao)
        except Exception as error:
            print(f"  -> perfil/solução falhou: {error}")

    print(
        f"\nPipeline concluído."
        f"\nEmpresas encontradas: {aceitas}/{alvo}"
    )

if __name__ == "__main__":
    main()
