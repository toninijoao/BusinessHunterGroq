interface Empresa {
  name: string;
  city: string;
  state: string;
  country: string;
  address: string;
  phone: string;
  instagram: string;
  facebook: string;
  google_maps: string;
  website: string;
  website_status: string;
  website_confidence: number;
  sources?: string[];
}

interface ResultadoItem {
  empresa: Empresa;
  erro?: string;
}

interface Candidata {
  nome: string;
  endereco: string;
  telefone: string;
  site: string;
}

interface RespostaCandidatas {
  candidatas: Candidata[];
}

interface RespostaProcessarCandidata {
  aceita: boolean;
  nome?: string;
  motivo?: string;
  empresa?: Empresa;
  erro_enriquecimento?: string;
}

interface EstadoIBGE {
  id: number;
  sigla: string;
  nome: string;
}

interface MunicipioIBGE {
  id: number;
  nome: string;
}

const IBGE_ESTADOS_URL =
  "https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome";

function urlMunicipios(uf: string): string {
  return `https://servicodados.ibge.gov.br/api/v1/localidades/estados/${uf}/municipios?orderBy=nome`;
}

const STATUS_LEGIVEL: Record<string, { texto: string; classe: string }> = {
  WEBSITE_NOT_FOUND: { texto: "Sem site", classe: "badge--ok" },
  WEBSITE_FOUND: { texto: "Tem site", classe: "badge--neutro" },
  WEBSITE_UNCERTAIN: { texto: "Incerto", classe: "badge--alerta" }
};

const selectEstado = document.querySelector<HTMLSelectElement>("#select-estado");
const selectCidade = document.querySelector<HTMLSelectElement>("#select-cidade");
const botao = document.querySelector<HTMLButtonElement>("#botao-iniciar");
const elementoStatus = document.querySelector<HTMLParagraphElement>("#status");
const corpoTabela = document.querySelector<HTMLTableSectionElement>("#corpo-tabela");

if (!selectEstado || !selectCidade || !botao || !elementoStatus || !corpoTabela) {
  throw new Error("Elementos da página não encontrados.");
}

async function carregarEstados(): Promise<void> {
  try {
    const resposta = await fetch(IBGE_ESTADOS_URL);
    const estados: EstadoIBGE[] = await resposta.json();

    selectEstado!.innerHTML = '<option value="">Selecione o estado</option>';

    estados.forEach((estado) => {
      const opcao = document.createElement("option");
      opcao.value = estado.sigla;
      opcao.textContent = `${estado.nome} (${estado.sigla})`;
      selectEstado!.appendChild(opcao);
    });
  } catch {
    selectEstado!.innerHTML = '<option value="">Falha ao carregar estados</option>';
  }
}

async function carregarCidades(uf: string): Promise<void> {
  selectCidade!.disabled = true;
  selectCidade!.innerHTML = '<option value="">Carregando...</option>';
  atualizarBotao();

  try {
    const resposta = await fetch(urlMunicipios(uf));
    const municipios: MunicipioIBGE[] = await resposta.json();

    selectCidade!.innerHTML = '<option value="">Selecione a cidade</option>';

    municipios.forEach((municipio) => {
      const opcao = document.createElement("option");
      opcao.value = municipio.nome;
      opcao.textContent = municipio.nome;
      selectCidade!.appendChild(opcao);
    });

    selectCidade!.disabled = false;
  } catch {
    selectCidade!.innerHTML = '<option value="">Falha ao carregar cidades</option>';
  } finally {
    atualizarBotao();
  }
}

function atualizarBotao(): void {
  botao!.disabled = !selectCidade!.value;
}

function limparTabela(): void {
  corpoTabela!.innerHTML = "";
}

interface ConfigPublica {
  quantidade_empresas: number;
}

let debugLogAcumulado: string[] = [];

function renderizarDebugLog(): void {
  const anterior = document.querySelector("#debug-log");
  anterior?.remove();

  if (debugLogAcumulado.length === 0) {
    return;
  }

  const detalhes = document.createElement("details");
  detalhes.id = "debug-log";

  const resumo = document.createElement("summary");
  resumo.textContent = "Ver detalhes técnicos da busca";
  detalhes.appendChild(resumo);

  const pre = document.createElement("pre");
  pre.textContent = debugLogAcumulado.join("\n");
  detalhes.appendChild(pre);

  elementoStatus!.insertAdjacentElement("afterend", detalhes);
}

function criarCelula(texto: string): HTMLTableCellElement {
  const celula = document.createElement("td");
  celula.textContent = texto;
  return celula;
}

function renderizarLinha(item: ResultadoItem): void {
  const linha = document.createElement("tr");

  if (item.erro) {
    linha.appendChild(criarCelula(item.empresa?.name ?? ""));
    const celulaErro = document.createElement("td");
    celulaErro.colSpan = 5;
    celulaErro.textContent = `Erro ao processar: ${item.erro}`;
    linha.appendChild(celulaErro);
    corpoTabela!.appendChild(linha);
    return;
  }

  const empresa = item.empresa;

  linha.appendChild(criarCelula(empresa.name || ""));
  linha.appendChild(
    criarCelula([empresa.city, empresa.state].filter(Boolean).join(" / "))
  );
  linha.appendChild(criarCelula(empresa.phone || ""));
  linha.appendChild(criarCelula(empresa.address || ""));

  const celulaMapa = document.createElement("td");
  if (empresa.google_maps) {
    const link = document.createElement("a");
    link.href = empresa.google_maps;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Ver mapa";
    celulaMapa.appendChild(link);
  }
  linha.appendChild(celulaMapa);

  const celulaStatus = document.createElement("td");
  const info = STATUS_LEGIVEL[empresa.website_status];
  const selo = document.createElement("span");
  selo.className = `badge ${info?.classe ?? "badge--neutro"}`;
  selo.textContent = info?.texto ?? empresa.website_status ?? "";
  celulaStatus.appendChild(selo);
  linha.appendChild(celulaStatus);

  corpoTabela!.appendChild(linha);
}

async function buscarCandidatasDaCidade(
  cidade: string,
  estado: string
): Promise<Candidata[]> {
  const parametros = new URLSearchParams({ cidade, estado });

  const resposta = await fetch(`/api/candidatas?${parametros.toString()}`);

  if (!resposta.ok) {
    const corpo = await resposta.text();
    throw new Error(`${resposta.status} - ${corpo}`);
  }

  const dados: RespostaCandidatas = await resposta.json();
  return dados.candidatas;
}

async function processarUmaCandidata(
  candidata: Candidata,
  cidade: string,
  estado: string
): Promise<RespostaProcessarCandidata> {
  const resposta = await fetch("/api/processar_candidata", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ candidata, cidade, estado })
  });

  if (!resposta.ok) {
    const corpo = await resposta.text();
    throw new Error(`${resposta.status} - ${corpo}`);
  }

  return resposta.json();
}

async function iniciarBusca(): Promise<void> {
  const cidade = selectCidade!.value;
  const estado = selectEstado!.value;

  if (!cidade) {
    return;
  }

  botao!.disabled = true;
  limparTabela();
  debugLogAcumulado = [];
  renderizarDebugLog();

  let totalAceitas = 0;

  try {
    const respostaConfig = await fetch("/api/config");

    if (!respostaConfig.ok) {
      throw new Error("Não foi possível carregar a configuração da busca.");
    }

    const config: ConfigPublica = await respostaConfig.json();
    const alvo = config.quantidade_empresas;

    elementoStatus!.textContent = `Buscando candidatas em ${cidade}...`;

    const candidatas = await buscarCandidatasDaCidade(cidade, estado);

    debugLogAcumulado.push(
      `${candidatas.length} candidata(s) encontrada(s) no total em ${cidade}.`
    );
    renderizarDebugLog();

    for (let i = 0; i < candidatas.length; i++) {
      if (totalAceitas >= alvo) {
        debugLogAcumulado.push(`Meta de ${alvo} empresas atingida, parando.`);
        break;
      }

      const candidata = candidatas[i];

      elementoStatus!.textContent =
        `Encontradas: ${totalAceitas}/${alvo} — verificando "${candidata.nome}" ` +
        `(candidata ${i + 1}/${candidatas.length})...`;

      try {
        const resultado = await processarUmaCandidata(
          candidata,
          cidade,
          estado
        );

        if (resultado.aceita && resultado.empresa) {
          totalAceitas += 1;
          renderizarLinha({ empresa: resultado.empresa });

          debugLogAcumulado.push(
            `Aceita "${resultado.nome ?? candidata.nome}"` +
              (resultado.erro_enriquecimento
                ? ` (perfil/solução falhou: ${resultado.erro_enriquecimento})`
                : "")
          );
        } else {
          debugLogAcumulado.push(
            `Rejeitada "${resultado.nome ?? candidata.nome}" — ${resultado.motivo}`
          );
        }
      } catch (erro) {
        debugLogAcumulado.push(
          `Erro em "${candidata.nome}" — ${(erro as Error).message}`
        );
      }

      renderizarDebugLog();
    }

    elementoStatus!.textContent =
      totalAceitas > 0
        ? `Busca concluída — ${totalAceitas}/${alvo} empresa(s) encontrada(s) em ${cidade}.`
        : `Busca concluída — nenhuma empresa encontrada em ${cidade}.`;
  } catch (erro) {
    elementoStatus!.textContent = `Falha ao executar a busca: ${(erro as Error).message}`;
  } finally {
    atualizarBotao();
  }
}

selectEstado.addEventListener("change", () => {
  const uf = selectEstado!.value;

  if (!uf) {
    selectCidade!.disabled = true;
    selectCidade!.innerHTML = '<option value="">Selecione o estado primeiro</option>';
    atualizarBotao();
    return;
  }

  void carregarCidades(uf);
});

selectCidade.addEventListener("change", atualizarBotao);

botao.addEventListener("click", () => {
  void iniciarBusca();
});

void carregarEstados();