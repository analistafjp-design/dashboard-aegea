/* =========================================================================
   Núcleo do Dashboard Executivo
   Estado dos filtros, chamadas à API, navegação sem recarregar, formatação
   numérica em português e componentes de UI reutilizáveis.
   ========================================================================= */
(function (window) {
  "use strict";

  const App = {};

  /* ------------------------------------------------------------- estado */
  App.estado = {
    filtros: {},
    pagina: document.body.dataset.pagina || "home",
    carregando: false,
  };

  const CHAVES_FILTRO = ["ano", "mes", "data_inicio", "data_fim", "cidade",
    "frente", "equipe", "regiao", "projeto", "setor"];

  App.lerFiltrosDaUrl = function () {
    const parametros = new URLSearchParams(window.location.search);
    const filtros = {};
    CHAVES_FILTRO.forEach((chave) => {
      const valor = parametros.get(chave);
      if (valor) filtros[chave] = valor;
    });
    App.estado.filtros = filtros;
    return filtros;
  };

  App.querystring = function (extras) {
    const parametros = new URLSearchParams();
    Object.entries(App.estado.filtros).forEach(([chave, valor]) => {
      if (valor !== null && valor !== undefined && valor !== "") parametros.set(chave, valor);
    });
    Object.entries(extras || {}).forEach(([chave, valor]) => {
      if (valor !== null && valor !== undefined && valor !== "") parametros.set(chave, valor);
    });
    const texto = parametros.toString();
    return texto ? `?${texto}` : "";
  };

  App.atualizarUrl = function () {
    const url = window.location.pathname + App.querystring();
    window.history.replaceState({ pagina: App.estado.pagina }, "", url);
  };

  /* ---------------------------------------------------------------- API */
  App.api = async function (caminho, opcoes) {
    const resposta = await fetch(caminho, Object.assign({
      headers: { Accept: "application/json" },
    }, opcoes || {}));
    let dados = null;
    try {
      dados = await resposta.json();
    } catch (erro) {
      dados = null;
    }
    if (!resposta.ok) {
      const mensagem = (dados && (dados.mensagem || dados.detail)) ||
        "Não foi possível carregar os dados.";
      throw new Error(mensagem);
    }
    return dados;
  };

  App.buscar = function (recurso, extras) {
    return App.api(`/api/${recurso}${App.querystring(extras)}`);
  };

  /* --------------------------------------------------------- formatação */
  const nf = (casas) => new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas, maximumFractionDigits: casas,
  });

  App.numero = function (valor, casas) {
    if (valor === null || valor === undefined || Number.isNaN(valor)) return "—";
    return nf(casas || 0).format(valor);
  };

  App.moeda = function (valor) {
    if (valor === null || valor === undefined) return "—";
    return "R$ " + nf(2).format(valor);
  };

  App.percentual = function (valor, casas) {
    if (valor === null || valor === undefined) return "—";
    return nf(casas === undefined ? 1 : casas).format(valor) + "%";
  };

  App.formatar = function (valor, formato, casas) {
    if (valor === null || valor === undefined) return "—";
    if (formato === "moeda") return App.moeda(valor);
    if (formato === "percentual") return App.percentual(valor, casas);
    return App.numero(valor, casas);
  };

  App.escapar = function (texto) {
    const div = document.createElement("div");
    div.textContent = texto === null || texto === undefined ? "" : String(texto);
    return div.innerHTML;
  };

  /* --------------------------------------------------------- componentes */
  App.cardKpi = function (indicador) {
    const semDados = !indicador.disponivel || indicador.valor === null;
    const valor = semDados
      ? `<div class="card__valor card__valor--sem-dados">${App.escapar(indicador.mensagem || "Sem dados")}</div>`
      : `<div class="card__valor">${App.escapar(indicador.texto)}</div>`;
    const variacao = indicador.variacao === null || indicador.variacao === undefined
      ? `<div class="card__variacao card__variacao--neutro">Sem base de comparação</div>`
      : `<div class="card__variacao card__variacao--${indicador.direcao}">
           ${App.escapar(indicador.texto_variacao)}
           <span class="card__comparacao">${App.escapar(indicador.rotulo_comparacao || "vs. período anterior")}</span>
         </div>`;
    const meta = (indicador.meta !== null && indicador.meta !== undefined)
      ? `<span class="selo selo--${indicador.status}">${App.escapar(indicador.rotulo_status)}</span>` : "";
    return `
      <div class="card card--${indicador.status}" title="${App.escapar(indicador.pergunta)}">
        <div class="card__faixa"></div>
        <div class="card__topo">
          <div class="card__titulo">${App.escapar(indicador.titulo)}</div>
          ${meta}
        </div>
        ${valor}
        ${variacao}
        ${indicador.explicacao ? `<div class="card__explicacao">${App.escapar(indicador.explicacao)}</div>` : ""}
      </div>`;
  };

  App.renderKpis = function (seletor, indicadores) {
    const alvo = document.querySelector(seletor);
    if (!alvo) return;
    alvo.innerHTML = (indicadores || []).map(App.cardKpi).join("") ||
      `<div class="vazio">Sem indicadores para o filtro selecionado.</div>`;
  };

  App.blocoMeta = function (bloco) {
    if (!bloco) return `<div class="vazio">Sem dados para o período.</div>`;
    const semMeta = bloco.meta === null || bloco.meta === undefined;
    const atingimento = bloco.atingimento === null || bloco.atingimento === undefined
      ? null : bloco.atingimento;
    const largura = atingimento === null ? 0 : Math.min(atingimento, 100);
    const ritmo = bloco.dias_uteis_decorridos && bloco.meta
      ? Math.min((bloco.meta_acumulada / bloco.meta) * 100, 100) : null;

    return `
      <div class="metas-grade">
        <div class="meta-box">
          <div class="meta-box__rotulo">Meta</div>
          <div class="meta-box__valor">${semMeta ? "—" : App.numero(bloco.meta)}</div>
          ${semMeta ? `<div class="painel__descricao">${App.escapar(bloco.mensagem_meta || "Meta não cadastrada")}</div>` : ""}
        </div>
        <div class="meta-box">
          <div class="meta-box__rotulo">Realizado</div>
          <div class="meta-box__valor">${App.numero(bloco.realizado)}</div>
        </div>
        <div class="meta-box">
          <div class="meta-box__rotulo">Falta</div>
          <div class="meta-box__valor">${semMeta ? "—" : App.numero(bloco.falta)}</div>
        </div>
        <div class="meta-box meta-box--${bloco.status}">
          <div class="meta-box__rotulo">Atingimento</div>
          <div class="meta-box__valor">${atingimento === null ? "—" : App.percentual(atingimento)}</div>
        </div>
      </div>
      <div class="progresso">
        <div class="progresso__trilho">
          <div class="progresso__barra progresso__barra--${bloco.status}" style="width:${largura}%"></div>
          ${ritmo !== null ? `<div class="progresso__marcador" style="left:${ritmo}%" title="Meta acumulada até hoje"></div>` : ""}
        </div>
        <div class="progresso__legenda">
          <span>0</span>
          <span>${bloco.meta_acumulada !== null && bloco.meta_acumulada !== undefined
            ? "Meta acumulada até hoje: " + App.numero(bloco.meta_acumulada) : ""}</span>
          <span>${semMeta ? "" : App.numero(bloco.meta)}</span>
        </div>
      </div>
      <div class="grade grade--3" style="margin-top:14px">
        ${App.miniInfo("Média por dia útil", App.numero(bloco.media_dia, 1))}
        ${App.miniInfo("Necessário por dia", bloco.necessario_por_dia === null || bloco.necessario_por_dia === undefined
          ? "—" : App.numero(bloco.necessario_por_dia, 1))}
        ${App.miniInfo("Projeção do mês", bloco.projecao === null || bloco.projecao === undefined
          ? "—" : App.numero(bloco.projecao),
          bloco.diferenca_projetada === null || bloco.diferenca_projetada === undefined ? "" :
          (bloco.diferenca_projetada >= 0 ? "▲ " : "▼ ") + App.numero(Math.abs(bloco.diferenca_projetada)) + " vs. meta")}
      </div>`;
  };

  App.miniInfo = function (rotulo, valor, extra) {
    return `<div class="meta-box">
      <div class="meta-box__rotulo">${App.escapar(rotulo)}</div>
      <div class="meta-box__valor" style="font-size:19px">${App.escapar(valor)}</div>
      ${extra ? `<div class="painel__descricao">${App.escapar(extra)}</div>` : ""}
    </div>`;
  };

  /**
   * Tabela genérica.
   * colunas: [{chave, titulo, tipo: texto|numero|moeda|percentual|status, casas, clique}]
   */
  App.tabela = function (seletor, colunas, registros, opcoes) {
    const alvo = document.querySelector(seletor);
    if (!alvo) return;
    opcoes = opcoes || {};
    if (!registros || !registros.length) {
      alvo.innerHTML = `<div class="tabela__vazia">${App.escapar(opcoes.vazio || "Sem dados para o filtro selecionado.")}</div>`;
      return;
    }
    const cabecalho = colunas.map((c) =>
      `<th class="${c.tipo && c.tipo !== "texto" && c.tipo !== "status" ? "num" : ""}">${App.escapar(c.titulo)}</th>`
    ).join("");

    const linhas = registros.map((registro) => {
      const celulas = colunas.map((coluna) => {
        const valor = registro[coluna.chave];
        if (coluna.tipo === "status") {
          const rotulos = { verde: "No alvo", amarelo: "Atenção", vermelho: "Crítico",
            azul: "Acompanhar", cinza: "Sem meta" };
          return `<td><span class="selo selo--${valor || "cinza"}">${rotulos[valor] || "—"}</span></td>`;
        }
        if (coluna.tipo && coluna.tipo !== "texto") {
          const texto = valor === null || valor === undefined
            ? (coluna.vazio || "—")
            : App.formatar(valor, coluna.tipo, coluna.casas);
          return `<td class="num">${App.escapar(texto)}</td>`;
        }
        const conteudo = App.escapar(valor === null || valor === undefined ? "—" : valor);
        return coluna.clique
          ? `<td><span class="clicavel" data-filtro="${coluna.clique}" data-valor="${App.escapar(valor)}">${conteudo}</span></td>`
          : `<td>${conteudo}</td>`;
      }).join("");
      return `<tr>${celulas}</tr>`;
    }).join("");

    alvo.innerHTML = `<div class="tabela-wrap"><table class="tabela">
      <thead><tr>${cabecalho}</tr></thead><tbody>${linhas}</tbody></table></div>`;

    alvo.querySelectorAll("[data-filtro]").forEach((elemento) => {
      elemento.addEventListener("click", () => {
        App.aplicarFiltro(elemento.dataset.filtro, elemento.dataset.valor);
      });
    });
  };

  /* -------------------------------------------------------------- toasts */
  App.toast = function (mensagem, tipo, titulo) {
    let caixa = document.querySelector(".toasts");
    if (!caixa) {
      caixa = document.createElement("div");
      caixa.className = "toasts";
      document.body.appendChild(caixa);
    }
    const item = document.createElement("div");
    item.className = `toast toast--${tipo || "info"}`;
    item.innerHTML = `${titulo ? `<div class="toast__titulo">${App.escapar(titulo)}</div>` : ""}
      <div>${App.escapar(mensagem)}</div>`;
    caixa.appendChild(item);
    setTimeout(() => item.remove(), tipo === "erro" ? 9000 : 5000);
  };

  App.carregando = function (seletor, texto) {
    const alvo = document.querySelector(seletor);
    if (alvo) {
      alvo.innerHTML = `<div class="carregando"><div class="spinner"></div>${App.escapar(texto || "Carregando...")}</div>`;
    }
  };

  App.vazio = function (seletor, texto) {
    const alvo = document.querySelector(seletor);
    if (alvo) alvo.innerHTML = `<div class="vazio">${App.escapar(texto)}</div>`;
  };

  /* -------------------------------------------------------------- filtros */
  App.aplicarFiltro = function (chave, valor) {
    if (!CHAVES_FILTRO.includes(chave)) return;
    if (valor === null || valor === "" || valor === undefined) {
      delete App.estado.filtros[chave];
    } else {
      App.estado.filtros[chave] = valor;
    }
    App.atualizarUrl();
    App.sincronizarFormulario();
    App.recarregarPagina();
    App.toast(`Filtro aplicado: ${chave} = ${valor}`, "info");
  };

  App.limparFiltros = function () {
    App.estado.filtros = {};
    App.atualizarUrl();
    App.sincronizarFormulario();
    App.recarregarPagina();
  };

  App.sincronizarFormulario = function () {
    const formulario = document.getElementById("form-filtros");
    if (!formulario) return;
    CHAVES_FILTRO.forEach((chave) => {
      const campo = formulario.elements[chave];
      if (campo) campo.value = App.estado.filtros[chave] || "";
    });
    App.renderResumoFiltros();
  };

  App.renderResumoFiltros = function () {
    const alvo = document.getElementById("resumo-filtros");
    if (!alvo) return;
    const rotulos = { ano: "Ano", mes: "Mês", data_inicio: "De", data_fim: "Até",
      cidade: "Cidade", frente: "Frente", equipe: "Equipe", regiao: "Região",
      projeto: "Projeto", setor: "Setor" };
    const chips = Object.entries(App.estado.filtros)
      .map(([chave, valor]) => `<span class="chip">${rotulos[chave] || chave}: ${App.escapar(valor)}</span>`);
    alvo.innerHTML = chips.length
      ? chips.join("") + `<span class="chip" style="cursor:pointer;background:var(--surface-3);color:var(--muted)" id="chip-limpar">limpar tudo ✕</span>`
      : "";
    const limpar = document.getElementById("chip-limpar");
    if (limpar) limpar.addEventListener("click", App.limparFiltros);
  };

  App.iniciarFiltros = function () {
    const formulario = document.getElementById("form-filtros");
    if (!formulario) return;
    formulario.addEventListener("submit", (evento) => {
      evento.preventDefault();
      const dados = new FormData(formulario);
      const filtros = {};
      CHAVES_FILTRO.forEach((chave) => {
        const valor = (dados.get(chave) || "").toString().trim();
        if (valor) filtros[chave] = valor;
      });
      App.estado.filtros = filtros;
      App.atualizarUrl();
      App.renderResumoFiltros();
      App.recarregarPagina();
    });
    const limpar = document.getElementById("btn-limpar-filtros");
    if (limpar) limpar.addEventListener("click", App.limparFiltros);
    App.sincronizarFormulario();
  };

  /* ------------------------------------------------------------ navegação */
  App.paginas = {};
  App.registrar = function (nome, iniciar) { App.paginas[nome] = iniciar; };

  App.recarregarPagina = function () {
    const iniciar = App.paginas[App.estado.pagina];
    if (typeof iniciar === "function") iniciar();
  };

  App.navegar = async function (rota, chave) {
    const alvo = document.getElementById("conteudo-pagina");
    if (!alvo) { window.location.href = rota; return; }
    const separador = App.querystring() ? "&" : "?";
    App.carregando("#conteudo-pagina", "Carregando página...");
    try {
      const resposta = await fetch(`${rota}${App.querystring()}${separador}fragmento=1`, {
        headers: { "X-Requisicao": "fragmento" },
      });
      if (!resposta.ok) throw new Error("Falha ao abrir a página.");
      alvo.innerHTML = await resposta.text();
      App.estado.pagina = chave;
      document.body.dataset.pagina = chave;
      window.history.pushState({ pagina: chave }, "", rota + App.querystring());
      App.marcarMenu(chave);
      App.atualizarTitulo(chave);
      App.recarregarPagina();
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (erro) {
      window.location.href = rota + App.querystring();
    }
  };

  App.marcarMenu = function (chave) {
    document.querySelectorAll(".sidebar__item").forEach((item) => {
      item.classList.toggle("ativo", item.dataset.chave === chave);
    });
  };

  App.atualizarTitulo = function (chave) {
    const item = document.querySelector(`.sidebar__item[data-chave="${chave}"]`);
    const titulo = document.getElementById("titulo-pagina");
    if (item && titulo) {
      titulo.textContent = item.dataset.titulo || item.textContent.trim();
      document.title = `${titulo.textContent} · Dashboard Executivo`;
    }
  };

  App.iniciarNavegacao = function () {
    document.querySelectorAll(".sidebar__item").forEach((item) => {
      item.addEventListener("click", (evento) => {
        evento.preventDefault();
        const rota = item.dataset.rota;
        if (item.dataset.chave === App.estado.pagina) return;
        App.navegar(rota, item.dataset.chave);
        const barra = document.querySelector(".sidebar");
        if (barra) barra.classList.remove("aberta");
        const overlay = document.querySelector(".overlay-mobile");
        if (overlay) overlay.remove();
      });
    });
    window.addEventListener("popstate", () => window.location.reload());

    const botaoMenu = document.getElementById("btn-menu");
    if (botaoMenu) {
      botaoMenu.addEventListener("click", () => {
        const barra = document.querySelector(".sidebar");
        barra.classList.toggle("aberta");
        if (barra.classList.contains("aberta")) {
          const overlay = document.createElement("div");
          overlay.className = "overlay-mobile";
          overlay.addEventListener("click", () => { barra.classList.remove("aberta"); overlay.remove(); });
          document.body.appendChild(overlay);
        } else {
          const overlay = document.querySelector(".overlay-mobile");
          if (overlay) overlay.remove();
        }
      });
    }
  };

  /* ----------------------------------------------------------------- tema */
  App.aplicarTema = function (tema) {
    document.documentElement.dataset.tema = tema === "escuro" ? "escuro" : "claro";
    try { localStorage.setItem("tema", tema); } catch (erro) { /* modo privado */ }
    if (window.Graficos) window.Graficos.redesenhar();
  };

  App.alternarTema = function () {
    const atual = document.documentElement.dataset.tema === "escuro" ? "claro" : "escuro";
    App.aplicarTema(atual);
    return atual;
  };

  /* ------------------------------------------------------------ exportar */
  App._carregarGeradorPdf = function () {
    if (window.html2pdf) return Promise.resolve(window.html2pdf);
    if (App._promessaGeradorPdf) return App._promessaGeradorPdf;
    const carregarScript = (origem) => new Promise((resolve, reject) => {
      const script = document.createElement("script");
      script.src = origem;
      script.onload = resolve;
      script.onerror = () => reject(new Error(
        "Não foi possível carregar o gerador de PDF instalado no dashboard."
      ));
      document.head.appendChild(script);
    });
    App._promessaGeradorPdf = carregarScript("/static/js/html2canvas.min.js?v=1.11.0")
      .then(() => carregarScript("/static/js/jspdf.umd.min.js?v=1.11.0"))
      .then(() => carregarScript("/static/js/html2pdf.min.js?v=1.11.0"))
      .then(() => window.html2pdf);
    return App._promessaGeradorPdf;
  };

  App.nomeArquivoPdf = function (recurso) {
    const agora = new Date();
    const dois = (valor) => String(valor).padStart(2, "0");
    const carimbo = `${agora.getFullYear()}${dois(agora.getMonth() + 1)}${dois(agora.getDate())}`;
    const nomes = { home: "venda_implantacao", termos: "termos_aplicados", geral: "dashboard_geral" };
    return `${nomes[recurso] || recurso}_${carimbo}.pdf`;
  };

  App.baixarPdfVisual = async function (elemento, nomeArquivo) {
    if (!elemento) throw new Error("A área do relatório não foi encontrada.");
    const gerador = await App._carregarGeradorPdf();
    if (!gerador) throw new Error("O gerador de PDF não ficou disponível.");
    document.body.classList.add("exportando-pdf");
    try {
      if (window.Graficos) {
        window.Graficos.redesenhar();
        await new Promise((resolve) => setTimeout(resolve, 450));
      }
      const largura = Math.max(elemento.scrollWidth, 1180);
      await gerador().set({
        margin: [5, 5, 5, 5],
        filename: nomeArquivo,
        image: { type: "jpeg", quality: 0.96 },
        html2canvas: {
          scale: 1.45,
          useCORS: true,
          backgroundColor: "#ffffff",
          logging: false,
          scrollX: 0,
          scrollY: 0,
          windowWidth: largura,
        },
        jsPDF: { unit: "mm", format: "a4", orientation: "landscape" },
        pagebreak: {
          mode: ["css", "legacy"],
          avoid: [".visual-simples", ".indicador-faixa", ".insight", ".titulo-faixa"],
        },
      }).from(elemento).save();
    } finally {
      document.body.classList.remove("exportando-pdf");
    }
  };

  App.exportar = function (recurso, formato, extras) {
    if (formato === "pdf") {
      if (recurso === "geral") {
        window.open(`/relatorio-geral${App.querystring(Object.assign(
          { baixar_pdf: 1 }, extras || {}
        ))}`, "_blank");
      } else {
        const elemento = document.querySelector(".app--simples");
        App.toast("Preparando a imagem completa da página...", "info", "Gerando PDF");
        App.baixarPdfVisual(elemento, App.nomeArquivoPdf(recurso)).catch((erro) => {
          App.toast(erro.message || "Não foi possível gerar o PDF.", "erro", "Falha no PDF");
        });
      }
      return;
    }
    const url = `/api/exportar/${recurso}${App.querystring(Object.assign({ formato }, extras || {}))}`;
    window.open(url, "_blank");
  };

  App.iniciarExportacao = function () {
    document.querySelectorAll("[data-exportar]").forEach((botao) => {
      botao.addEventListener("click", () => {
        const recurso = botao.dataset.exportar === "atual"
          ? App.estado.pagina : botao.dataset.exportar;
        App.exportar(recurso, botao.dataset.formato || "xlsx");
      });
    });
  };

  /* ------------------------------------------------------------- arranque */
  App.iniciar = function () {
    App.lerFiltrosDaUrl();
    App.iniciarFiltros();
    App.iniciarNavegacao();
    App.iniciarExportacao();
    App.recarregarPagina();
  };

  window.App = App;
})(window);
