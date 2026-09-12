import json
from pathlib import Path
import yaml
from agentes.agente_hunter import executar_hunter
from agentes.agente_filtro import executar_filtro
from agentes.agente_arquiteto import executar_arquiteto
from agentes.agente_planilha import executar_planilha

base_dir = Path(__file__).resolve().parent.parent
config_path = base_dir / "config" / "config.yaml"

def carregar_config() -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")

    with config_path.open("r", encoding="utf-8") as arquivo:
        return yaml.safe_load(arquivo)

def criar_tarefa(config: dict, cidade: str, estado: str) -> str:
    quantidade = config.get("quantidade_empresas", 20)
    segmentos = config.get("segmentos", [])

    if not cidade or not cidade.strip():
        raise ValueError(
            "Nenhuma cidade foi informada."
        )

    if not segmentos:
        raise ValueError(
            "Nenhum segmento foi configurado."
        )

    localizacao = f"{cidade} - {estado}" if estado else cidade

    segmentos_formatados = "\n".join(
        f"- {segmento}"
        for segmento in segmentos
    )

    return f"""
    Encontre até {quantidade} empresas de pequeno ou médio porte em
    {localizacao}, no Brasil.

    Segmentos permitidos:
    {segmentos_formatados}

    Critérios obrigatórios:

    - A empresa deve estar ativa.
    - A empresa deve pertencer a um dos segmentos configurados.
    - A empresa deve ser de pequeno ou médio porte, quando isso puder ser estimado.
    - A empresa não deve possuir um site oficial funcional.
    - Não considere Instagram, Facebook, Google Maps, diretórios ou marketplaces como site oficial.
    - Não inclua empresas já existentes no banco de dados.
    - Valide cuidadosamente a ausência de um site antes de considerar a empresa válida.
    - Não invente informações.
    - Pesquise somente em {localizacao}. Não pesquise em outras cidades.

    Retorne somente empresas que atendam aos critérios.

    ATENÇÃO - PRIMEIRO PASSO OBRIGATÓRIO:
    Você ainda não pesquisou nada. É PROIBIDO responder com {{"empresas": []}}
    ou qualquer resultado final antes de chamar a ferramenta pesquisar_web
    pelo menos uma vez para cada segmento permitido em {localizacao}.
    "Não invento dados" significa usar as ferramentas para descobrir dados
    reais - NÃO significa deixar de pesquisar e responder vazio.
    Comece agora mesmo chamando pesquisar_web com UM segmento e UMA
    localização, no formato '<segmento> em <cidade>'.
"""

def executar_pipeline(
    tarefa: str,
    segmentos: list | None = None,
    cidade: str | None = None
) -> dict:
    empresas = executar_hunter(tarefa, segmentos=segmentos, cidade=cidade)

    if not isinstance(empresas, dict):
        raise ValueError(
            "O hunter não retornou um objeto válido."
        )

    lista_empresas = empresas.get("empresas", [])
    debug_log = empresas.get("debug_log", [])
    erro_hunter = empresas.get("erro")

    if not isinstance(lista_empresas, list):
        raise ValueError(
            "O campo 'empresas' retornado pelo Hunter deve ser uma lista."
        )

    resultados = []

    for empresa in lista_empresas:
        try:
            perfil = executar_filtro(empresa)
            solucao = executar_arquiteto(perfil)
            dados_planilha = executar_planilha(empresa, perfil, solucao)
            resultados.append(
                {
                    "empresa": empresa,
                    "perfil": perfil,
                    "solucao": solucao,
                    "planilha": dados_planilha
                }
            )

        except Exception as error:
            resultados.append(
                {
                    "empresa": empresa,
                    "erro": str(error)
                }
            )

    return {
        "quantidade_encontrada": len(lista_empresas),
        "quantidade_processada": len(resultados),
        "resultados": resultados,
        "erro_hunter": erro_hunter,
        "debug_log": debug_log
    }

if __name__ == "__main__":
    config = carregar_config()
    cidade = input("Cidade: ").strip()
    estado = input("Estado (UF, opcional): ").strip()
    tarefa = criar_tarefa(config, cidade=cidade, estado=estado)
    resultado = executar_pipeline(
        tarefa,
        segmentos=config.get("segmentos"),
        cidade=cidade
    )

    print(json.dumps(resultado, ensure_ascii=False, indent=4))