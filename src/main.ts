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

interface ResultadoPipeline {
  quantidade_encontrada: number;
  quantidade_processada: number;
  resultados: ResultadoItem[];
  erro_hunter?: string | null;
  debug_log?: string[];
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

function renderizarDebugLog(resultado: ResultadoPipeline): void {

  const anterior = document.querySelector("#debug-log");
  anterior?.remove();

  if (!resultado.debug_log || resultado.debug_log.length === 0) {
    return;
  }

  const detalhes = document.createElement("details");
  detalhes.id = "debug-log";

  const resumo = document.createElement("summary");
  resumo.textContent = resultado.erro_hunter
    ? "Ver detalhes técnicos (um erro ocorreu)"
    : "Ver detalhes técnicos da busca";
  detalhes.appendChild(resumo);

  if (resultado.erro_hunter) {
    const erro = document.createElement("p");
    erro.className = "debug-erro";
    erro.textContent = resultado.erro_hunter;
    detalhes.appendChild(erro);
  }

  const pre = document.createElement("pre");
  pre.textContent = resultado.debug_log.join("\n");
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

async function iniciarBusca(): Promise<void> {
  const cidade = selectCidade!.value;
  const estado = selectEstado!.value;

  if (!cidade) {
    return;
  }

  botao!.disabled = true;
  elementoStatus!.textContent = `Buscando em ${cidade} - ${estado}... isso pode levar alguns minutos.`;
  limparTabela();
  document.querySelector("#debug-log")?.remove();

  try {
    const resposta = await fetch("/api/executar", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ cidade, estado })
    });

    if (!resposta.ok) {
      const corpo = await resposta.text();
      throw new Error(`${resposta.status} - ${corpo}`);
    }

    const resultado: ResultadoPipeline = await resposta.json();

    renderizarDebugLog(resultado);

    if (resultado.resultados.length === 0) {
      elementoStatus!.textContent = resultado.erro_hunter
        ? "A busca não foi concluída — veja os detalhes técnicos abaixo."
        : "Nenhuma empresa encontrada.";
      return;
    }

    resultado.resultados.forEach(renderizarLinha);

    elementoStatus!.textContent =
      `${resultado.quantidade_encontrada} empresa(s) encontrada(s), ` +
      `${resultado.quantidade_processada} processada(s).`;

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
