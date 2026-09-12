from orquestrador.orquestrador import carregar_config, criar_tarefa, executar_pipeline

def main():
    config = carregar_config()

    cidade = input("Cidade: ").strip()
    estado = input("Estado (UF, opcional): ").strip()

    tarefa = criar_tarefa(config, cidade=cidade, estado=estado)

    resultado = executar_pipeline(
        tarefa,
        segmentos=config.get("segmentos"),
        cidade=cidade
    )

    print(
        f"\nPipeline concluído."
        f"\nEmpresas encontradas: {resultado['quantidade_encontrada']}"
        f"\nEmpresas processadas: {resultado['quantidade_processada']}"
    )

if __name__ == "__main__":
    main()
