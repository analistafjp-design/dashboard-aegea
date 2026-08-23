/* =========================================================================
   Gráficos (Plotly) — layout único, limpo e com suporte a tema claro/escuro.
   ========================================================================= */
(function (window) {
  "use strict";

  const Graficos = {};
  const registrados = new Map();

  const PALETA = ["#1257b8", "#3fa9f5", "#128a52", "#b57500", "#7a4fd4", "#c62828", "#00867d"];

  function cores() {
    const escuro = document.documentElement.dataset.tema === "escuro";
    return {
      texto: escuro ? "#c9d6e6" : "#43516b",
      grade: escuro ? "#263449" : "#e6ebf3",
      fundo: "rgba(0,0,0,0)",
      linha: escuro ? "#4b90f0" : "#1257b8",
      meta: escuro ? "#e5a53a" : "#b57500",
      sucesso: escuro ? "#3fc383" : "#128a52",
      escuro,
    };
  }

  function layoutBase(extra) {
    const c = cores();
    return Object.assign({
      paper_bgcolor: c.fundo,
      plot_bgcolor: c.fundo,
      font: { family: '"Segoe UI", Roboto, Arial, sans-serif', size: 12, color: c.texto },
      margin: { l: 52, r: 18, t: 18, b: 44 },
      hovermode: "x unified",
      hoverlabel: { bgcolor: c.escuro ? "#1e2b3d" : "#ffffff", bordercolor: c.grade,
        font: { color: c.texto, size: 12 } },
      legend: { orientation: "h", y: -0.18, x: 0, font: { size: 11.5 } },
      xaxis: { gridcolor: c.grade, zeroline: false, automargin: true },
      yaxis: { gridcolor: c.grade, zeroline: false, automargin: true,
        separatethousands: true, tickformat: ",.0f" },
      colorway: PALETA,
    }, extra || {});
  }

  const CONFIG = {
    displaylogo: false,
    responsive: true,
    locale: "pt-br",
    modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d", "toggleSpikelines"],
    toImageButtonOptions: { format: "png", filename: "grafico-dashboard", scale: 2 },
  };

  /** Um traço tem dados se possui pontos em qualquer eixo suportado
      (barras/linhas usam x, rosca usa labels/values, funil usa x/y). */
  function temDados(serie) {
    const listas = [serie.x, serie.y, serie.labels, serie.values];
    return listas.some((lista) => Array.isArray(lista) && lista.length > 0)
      || Number.isFinite(Number(serie.value));
  }

  function rotuloValor(valor) {
    const numero = Number(valor);
    if (!Number.isFinite(numero) || numero === 0) return "";
    return numero.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  }

  function desenhar(id, series, layout) {
    const alvo = document.getElementById(id);
    if (!alvo) return;
    if (!series || !series.length || !series.some(temDados)) {
      alvo.innerHTML = '<div class="vazio">Sem dados para o filtro selecionado.</div>';
      registrados.delete(id);
      return;
    }
    registrados.set(id, { series, layout });
    window.Plotly.react(alvo, series, layoutBase(layout), CONFIG);
  }

  Graficos.redesenhar = function () {
    registrados.forEach((conteudo, id) => {
      const alvo = document.getElementById(id);
      if (alvo) window.Plotly.react(alvo, conteudo.series, layoutBase(conteudo.layout), CONFIG);
    });
  };

  Graficos.limpar = function (id) {
    const alvo = document.getElementById(id);
    if (alvo) { window.Plotly.purge(alvo); alvo.innerHTML = ""; }
    registrados.delete(id);
  };

  /** Barras verticais simples. */
  Graficos.barras = function (id, rotulos, valores, opcoes) {
    opcoes = opcoes || {};
    const c = cores();
    desenhar(id, [{
      type: "bar", x: rotulos, y: valores,
      marker: { color: opcoes.cor || c.linha, line: { width: 0 } },
      name: opcoes.nome || "Realizado",
      hovertemplate: "%{x}<br><b>%{y:,.0f}</b><extra></extra>",
      text: opcoes.mostrarValores ? valores.map((v) => v.toLocaleString("pt-BR")) : undefined,
      textposition: opcoes.mostrarValores ? "outside" : undefined,
    }], opcoes.layout);
  };

  /** Barras horizontais — ideal para rankings. */
  Graficos.barrasHorizontais = function (id, rotulos, valores, opcoes) {
    opcoes = opcoes || {};
    const c = cores();
    desenhar(id, [{
      type: "bar", orientation: "h",
      y: rotulos.slice().reverse(), x: valores.slice().reverse(),
      marker: { color: opcoes.cor || c.linha },
      text: valores.slice().reverse().map(rotuloValor),
      texttemplate: "%{text}", textposition: "outside", cliponaxis: false,
      hovertemplate: "%{y}<br><b>%{x:,.0f}</b><extra></extra>",
    }], Object.assign({
      margin: { l: Math.min(190, 12 + Math.max.apply(null, rotulos.map((r) => String(r).length)) * 7.2),
        r: 42, t: 12, b: 36 },
      hovermode: "closest",
      xaxis: { gridcolor: cores().grade, tickformat: ",.0f" },
    }, opcoes.layout));
  };

  /** Realizado x Meta por mês. */
  Graficos.realizadoMeta = function (id, rotulos, realizado, meta) {
    const c = cores();
    const series = [{
      type: "bar", name: "Realizado", x: rotulos, y: realizado,
      marker: { color: c.linha },
      hovertemplate: "%{x}<br>Realizado: <b>%{y:,.0f}</b><extra></extra>",
    }];
    if (meta && meta.some((v) => v !== null && v !== undefined)) {
      series.push({
        type: "scatter", mode: "lines+markers", name: "Meta", x: rotulos, y: meta,
        line: { color: c.meta, width: 2, dash: "dot" }, marker: { size: 7 },
        hovertemplate: "%{x}<br>Meta: <b>%{y:,.0f}</b><extra></extra>",
      });
    }
    desenhar(id, series, { barmode: "group" });
  };

  /** Linha diária + acumulado (eixo secundário). */
  Graficos.diarioAcumulado = function (id, datas, diario, acumulado, metaAcumulada) {
    const c = cores();
    const series = [
      { type: "bar", name: "Realizado no dia", x: datas, y: diario,
        marker: { color: c.linha, opacity: 0.85 },
        hovertemplate: "%{x}<br>Dia: <b>%{y:,.0f}</b><extra></extra>" },
      { type: "scatter", mode: "lines", name: "Acumulado", x: datas, y: acumulado,
        yaxis: "y2", line: { color: c.sucesso, width: 2.5 },
        hovertemplate: "Acumulado: <b>%{y:,.0f}</b><extra></extra>" },
    ];
    if (metaAcumulada && metaAcumulada.length) {
      series.push({ type: "scatter", mode: "lines", name: "Meta acumulada",
        x: datas, y: metaAcumulada, yaxis: "y2",
        line: { color: c.meta, width: 2, dash: "dot" },
        hovertemplate: "Meta acumulada: <b>%{y:,.0f}</b><extra></extra>" });
    }
    desenhar(id, series, {
      yaxis2: { overlaying: "y", side: "right", gridcolor: "rgba(0,0,0,0)",
        tickformat: ",.0f", automargin: true },
      margin: { l: 52, r: 56, t: 18, b: 44 },
    });
  };

  /** Rosca para composição (frentes, situações). */
  Graficos.rosca = function (id, rotulos, valores) {
    desenhar(id, [{
      type: "pie", hole: 0.62, labels: rotulos, values: valores,
      textinfo: "value+percent", textposition: "inside",
      texttemplate: "<b>%{value:,.0f}</b><br>%{percent}",
      marker: { colors: PALETA, line: { width: 1, color: cores().escuro ? "#141d2b" : "#fff" } },
      hovertemplate: "%{label}<br><b>%{value:,.0f}</b> (%{percent})<extra></extra>",
    }], { margin: { l: 10, r: 10, t: 10, b: 10 }, hovermode: "closest",
      legend: { orientation: "v", x: 1, y: 0.5, xanchor: "left" } });
  };

  /** Anel executivo compacto: realizado, percentual e meta no centro. */
  Graficos.anelMeta = function (id, realizado, meta) {
    const c = cores();
    const atual = Number(realizado) || 0;
    const alvo = Number(meta) || 0;
    const falta = Math.max(alvo - atual, 0);
    const percentual = alvo > 0 ? (atual / alvo) * 100 : 0;
    const base = alvo > 0 ? [Math.min(atual, alvo), falta] : [atual];
    const rotulos = alvo > 0 ? ["Realizado", "A realizar"] : ["Realizado"];
    desenhar(id, [{
      type: "pie", hole: 0.78, labels: rotulos, values: base,
      sort: false, direction: "clockwise", textinfo: "none",
      marker: { colors: [c.linha, c.escuro ? "#263449" : "#e8eef7"],
        line: { width: 0 } },
      hovertemplate: "%{label}<br><b>%{value:,.0f}</b><extra></extra>",
    }], {
      margin: { l: 8, r: 8, t: 5, b: 8 }, hovermode: "closest", showlegend: false,
      annotations: [{
        x: 0.5, y: 0.5, showarrow: false, align: "center",
        text: `<b>${atual.toLocaleString("pt-BR")}</b><br>`
          + `<span style="font-size:11px">${percentual.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% da meta</span>`
          + (alvo ? `<br><span style="font-size:10px;color:${c.texto}">Meta ${alvo.toLocaleString("pt-BR")}</span>` : ""),
        font: { size: 20, color: c.escuro ? "#eaf0f8" : "#0b3c7d" },
      }],
    });
  };

  /** Barra bullet: leitura rápida do avanço em relação à meta. */
  Graficos.barraMeta = function (id, realizado, meta) {
    const c = cores();
    const atual = Number(realizado) || 0;
    const alvo = Number(meta) || 0;
    const limite = Math.max(atual, alvo, 1) * 1.08;
    const percentual = alvo > 0 ? (atual / alvo) * 100 : 0;
    desenhar(id, [{
      type: "indicator", mode: "number+gauge", value: atual,
      number: { valueformat: ",.0f", font: { size: 25, color: c.escuro ? "#eaf0f8" : "#0b3c7d" } },
      title: { text: alvo
        ? `<span style="font-size:11px">${percentual.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% da meta · Meta ${alvo.toLocaleString("pt-BR")}</span>`
        : "<span style=\"font-size:11px\">Meta não cadastrada</span>" },
      gauge: {
        shape: "bullet", axis: { range: [0, limite], visible: false },
        bgcolor: c.escuro ? "#263449" : "#e8eef7", borderwidth: 0,
        bar: { color: atual >= alvo && alvo > 0 ? c.sucesso : c.linha, thickness: 0.58 },
        threshold: alvo > 0 ? { line: { color: c.meta, width: 3 }, thickness: 0.8, value: alvo } : undefined,
      },
      domain: { x: [0.06, 0.94], y: [0.2, 0.88] },
    }], { margin: { l: 10, r: 10, t: 4, b: 6 }, hovermode: "closest" });
  };

  /** Funil de faturamento. */
  Graficos.funil = function (id, etapas, valores) {
    desenhar(id, [{
      type: "funnel", y: etapas, x: valores,
      marker: { color: PALETA },
      textinfo: "value+percent initial",
      hovertemplate: "%{y}<br><b>%{x:,.0f}</b><extra></extra>",
    }], { margin: { l: 130, r: 24, t: 12, b: 24 }, hovermode: "closest" });
  };

  /** Comparativo agrupado (Serviços x VCG, Meta x Realizado). */
  Graficos.agrupado = function (id, rotulos, series) {
    desenhar(id, series.map((s, indice) => ({
      type: "bar", name: s.nome, x: rotulos, y: s.valores,
      marker: { color: s.cor || PALETA[indice % PALETA.length] },
      hovertemplate: "%{x}<br>" + s.nome + ": <b>%{y:,.0f}</b><extra></extra>",
    })), { barmode: "group" });
  };

  /** Produção diária empilhada por frente com a referência da meta diária. */
  Graficos.empilhadoComMeta = function (id, rotulos, series, meta) {
    const c = cores();
    const traces = series.map((s, indice) => ({
      type: "bar", name: s.nome, x: rotulos, y: s.valores,
      marker: { color: s.cor || PALETA[indice % PALETA.length] },
      text: s.valores.map(rotuloValor), texttemplate: "%{text}",
      textposition: "auto", cliponaxis: false,
      hovertemplate: "%{x}<br>" + s.nome + ": <b>%{y:,.0f}</b><extra></extra>",
    }));
    if (meta && meta.some((valor) => valor !== null && valor !== undefined)) {
      traces.push({
        type: "scatter", mode: "lines+markers", name: "Meta diária",
        x: rotulos, y: meta, line: { color: c.meta, width: 2.4, dash: "dot" },
        marker: { size: 6 },
        hovertemplate: "%{x}<br>Meta diária: <b>%{y:,.1f}</b><extra></extra>",
      });
    }
    desenhar(id, traces, { barmode: "stack", hovermode: "x unified" });
  };

  /** Comparativo horizontal empilhado, usado para Serviços x VCG por cidade. */
  Graficos.empilhadoHorizontal = function (id, rotulos, series) {
    const invertidos = rotulos.slice().reverse();
    desenhar(id, series.map((s, indice) => ({
      type: "bar", orientation: "h", name: s.nome,
      y: invertidos, x: s.valores.slice().reverse(),
      marker: { color: s.cor || PALETA[indice % PALETA.length] },
      text: s.valores.slice().reverse().map(rotuloValor),
      texttemplate: "%{text}", textposition: "auto", cliponaxis: false,
      hovertemplate: "%{y}<br>" + s.nome + ": <b>%{x:,.0f}</b><extra></extra>",
    })), {
      barmode: "stack", hovermode: "y unified",
      margin: {
        l: Math.min(190, 12 + Math.max.apply(null, rotulos.map((r) => String(r).length)) * 7.2),
        r: 24, t: 12, b: 36,
      },
      xaxis: { gridcolor: cores().grade, tickformat: ",.0f" },
    });
  };

  /** Linhas múltiplas (evolução por módulo). */
  Graficos.linhas = function (id, rotulos, series) {
    desenhar(id, series.map((s, indice) => ({
      type: "scatter", mode: "lines+markers", name: s.nome, x: rotulos, y: s.valores,
      line: { width: 2.4, color: s.cor || PALETA[indice % PALETA.length] },
      marker: { size: 6 },
      hovertemplate: "%{x}<br>" + s.nome + ": <b>%{y:,.0f}</b><extra></extra>",
    })), {});
  };

  window.Graficos = Graficos;
})(window);
