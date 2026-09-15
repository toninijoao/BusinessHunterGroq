from orquestrador.candidatos import listar_candidatas, processar_candidata
from tools.database import listar_empresas_por_cidade
from agentes.agente_filtro import executar_filtro
from agentes.agente_arquiteto import executar_arquiteto
from agentes.agente_planilha import executar_planilha


def main():
    cidade = input("Cidade: ").strip()
    estado = input("Estado (UF, opcional): ").strip()

    ja_salvas = listar_empresas_por_cidade(cidade)
    print(f"\n{len(ja_salvas)} empresa(s) já salva(s) de buscas anteriores em {cidade}:")
    for empresa in ja_salvas:
        print(f"  - {empresa.get('name')}")

    print(f"\nBuscando novas candidatas em {cidade}...")
    candidatas = listar_candidatas(cidade)
    print(f"{len(candidatas)} candidata(s) encontrada(s) no total.\n")

    aceitas = 0

    for candidata in candidatas:

        print(f"Verificando: {candidata.get('nome')}...")
        resultado = processar_candidata(candidata, cidade=cidade, estado=estado)

        if not resultado.get("aceita"):
            print(f"  -> rejeitada ({resultado.get('motivo')})")
            continue

        aceitas += 1
        empresa = resultado["empresa"]
        print(f"  -> ACEITA: {empresa['name']}")

        try:
            perfil = executar_filtro(empresa)
            solucao = executar_arquiteto(perfil)
            executar_planilha(empresa, perfil, solucao)
        except Exception as error:
            print(f"  -> perfil/solução falhou: {error}")

    print(
        f"\nPipeline concluído."
        f"\nEmpresas novas encontradas: {aceitas}"
        f"\nTotal na cidade (novas + antigas): {aceitas + len(ja_salvas)}"
    )

if __name__ == "__main__":
    main()
