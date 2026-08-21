/* =========================================================================
   Inicialização de cada página do dashboard.
   Cada função busca o JSON do módulo e preenche os componentes da tela.
   ========================================================================= */
(function (window) {
  "use strict";

  const App = window.App;
  const G = window.Graficos;

  function periodoTexto(dados, seletor) {
    const alvo = document.querySelector(seletor);
    if (alvo && dados.periodo) alvo.textContent = dados.periodo.rotulo;
  }

  function erro(seletor, mensagem) {
    const alvo = document.querySelector(seletor);
    if (alvo) alvo.innerHTML = `<div class="aviso aviso--erro"><span>✕</span><div>${App.escapar(mensagem)}</div></div>`;
    App.toast(mensagem, "erro", "Falha ao carregar");
  }

  function serieMensal(registros) {
    return {
      rotulos: (registros || []).map((r) => r.rotulo),
      valores: (registros || []).map((r) => r.total),
    };
  }

  function serieDiaria(registros) {
    return {
      datas: (registros || []).map((r) => r.data),
      diario: (registros || []).map((r) => r.total),
      acumulado: (registros || []).map((r) => r.acumulado),
    };
  }

  function ranking(registros, dimensao) {
    return {
      rotulos: (registros || []).map((r) => r[dimensao]),
      valores: (registros || []).map((r) => r.total),
    };
  }

  /** Linha da matriz META / REALIZADO / FALTA. */
  function matrizMeta(seletor, blocos) {
    App.tabela(seletor, [
      { chave: "rotulo", titulo: "Frente" },
      { chave: "meta", titulo: "Meta", tipo: "numero", vazio: "Não cadastrada" },
      { chave: "realizado", titulo: "Realizado", tipo: "numero" },
      { chave: "falta", titulo: "Falta", tipo: "numero", vazio: "—" },
      { chave: "atingimento", titulo: "% Meta", tipo: "percentual" },
      { chave: "status", titulo: "Status", tipo: "status" },
    ], blocos, { vazio: "Sem metas ou realizado para o período." });
  }

  /* ------------------------------------------------------------------ HOME */
  App.registrar("home", async function () {
    App.carregando("#home-cards");
    try {
      const dados = await App.buscar("home");
      periodoTexto(dados, "#home-periodo");

      const c = dados.consolidado;
      document.getElementById("home-consolidado").innerHTML = App.blocoMeta({
        meta: c.meta, realizado: c.realizado, falta: c.falta, atingimento: c.atingimento,
        status: c.status, projecao: c.projecao, diferenca_projetada: c.diferenca_projetada,
        media_dia: c.realizado !== null && dados.periodo.dias_uteis_decorridos
          ? c.realizado / dados.periodo.dias_uteis_decorridos : null,
        necessario_por_dia: (c.meta !== null && c.realizado !== null && c.dias_uteis_restantes)
          ? Math.max(c.meta - c.realizado, 0) / c.dias_uteis_restantes : null,
        meta_acumulada: c.meta !== null && dados.periodo.dias_uteis_totais
          ? c.meta * (dados.periodo.dias_uteis_decorridos / dados.periodo.dias_uteis_totais) : null,
        mensagem_meta: c.mensagem_meta,
        dias_uteis_decorridos: dados.periodo.dias_uteis_decorridos,
      });

      App.renderKpis("#home-cards", dados.cards);

      document.getElementById("home-modulos").innerHTML = dados.modulos.map((m) => `
        <div class="card card--${m.status}">
          <div class="card__faixa"></div>
          <div class="card__topo">
            <div class="card__titulo">${App.escapar(m.rotulo)}</div>
            <span class="selo selo--${m.status}">${m.atingimento === null ? "Sem meta"
              : App.percentual(m.atingimento)}</span>
          </div>
          <div class="card__valor">${m.realizado === null ? "Sem dados" : App.numero(m.realizado)}</div>
          <div class="card__explicacao">
            Meta: ${m.meta === null ? (m.mensagem_meta || "não cadastrada") : App.numero(m.meta)} ·
            Falta: ${m.falta === null ? "—" : App.numero(m.falta)} ·
            Projeção: ${m.projecao === null ? "—" : App.numero(m.projecao)}
          </div>
        </div>`).join("");

      const meses = {};
      Object.values(dados.evolucao).forEach((lista) =>
        (lista || []).forEach((r) => { meses[r.ano_mes] = r.rotulo; }));
      const chaves = Object.keys(meses).sort();
      const rotulos = chaves.map((k) => meses[k]);
      const linha = (lista) => {
        const mapa = {};
        (lista || []).forEach((r) => { mapa[r.ano_mes] = r.total; });
        return chaves.map((k) => (k in mapa ? mapa[k] : null));
      };
      G.linhas("graf-home-evolucao", rotulos, [
        { nome: "Termos", valores: linha(dados.evolucao.termos) },
        { nome: "Venda", valores: linha(dados.evolucao.vendas) },
        { nome: "Implantação", valores: linha(dados.evolucao.implantacao) },
      ]);

      const icones = { positivo: "▲", alerta: "▼", info: "•" };
      document.getElementById("home-insights").innerHTML = dados.insights.length
        ? dados.insights.slice(0, 8).map((i) => `
            <div class="insight insight--${i.tipo}">
              <span class="insight__icone">${icones[i.tipo] || "•"}</span>
              <div>${App.escapar(i.texto)}</div>
            </div>`).join("")
        : `<div class="vazio">Sem insights: não há dados suficientes no período.</div>`;

      document.getElementById("home-alertas").innerHTML = dados.alertas.length
        ? dados.alertas.map((a) => `
            <div class="alerta-item alerta-item--${a.categoria}">
              <span>${a.icone}</span>
              <div><div class="alerta-item__titulo">${App.escapar(a.titulo)}</div>
                <div class="alerta-item__descricao">${App.escapar(a.descricao)}</div></div>
            </div>`).join("")
        : `<div class="vazio">Nenhum alerta no período.</div>`;

      App.tabela("#home-top-cidades", [
        { chave: "cidade", titulo: "Cidade", clique: "cidade" },
        { chave: "total", titulo: "Implantação", tipo: "numero" },
      ], dados.top_cidades);

      App.tabela("#home-top-equipes", [
        { chave: "equipe", titulo: "Equipe", clique: "equipe" },
        { chave: "total", titulo: "Produção", tipo: "numero" },
      ], dados.top_equipes);
    } catch (e) {
      erro("#home-cards", e.message);
    }
  });

  /* ---------------------------------------------------------------- TERMOS */
  App.registrar("termos", async function () {
    App.carregando("#termos-cards");
    try {
      const dados = await App.buscar("modulo/termos");
      periodoTexto(dados, "#termos-periodo");
      document.getElementById("termos-bloco").innerHTML = App.blocoMeta(dados.bloco_principal);
      App.renderKpis("#termos-cards", dados.indicadores);
      matrizMeta("#termos-matriz", dados.blocos_meta);

      const mensal = serieMensal(dados.evolucao_mensal);
      G.realizadoMeta("graf-termos-mensal", mensal.rotulos, mensal.valores, null);

      const diario = serieDiaria(dados.evolucao_diaria);
      const metaAcum = dados.bloco_principal.meta
        ? diario.datas.map((_, i) => dados.bloco_principal.meta *
            ((i + 1) / Math.max(diario.datas.length, 1)))
        : null;
      G.diarioAcumulado("graf-termos-diario", diario.datas, diario.diario, diario.acumulado, metaAcum);

      const cidade = ranking(dados.por_cidade, "cidade");
      G.barrasHorizontais("graf-termos-cidade", cidade.rotulos, cidade.valores);

      const setor = ranking(dados.por_setor, "setor");
      G.barrasHorizontais("graf-termos-setor", setor.rotulos, setor.valores);

      const status = ranking(dados.por_status, "status_termo");
      G.rosca("graf-termos-status", status.rotulos, status.valores);

      App.tabela("#termos-tabela-cidade", [
        { chave: "cidade", titulo: "Cidade", clique: "cidade" },
        { chave: "total", titulo: "Termos", tipo: "numero" },
        { chave: "participacao", titulo: "Participação", tipo: "percentual" },
      ], dados.por_cidade);
    } catch (e) {
      erro("#termos-cards", e.message);
    }
  });

  /* ----------------------------------------------------------- FATURAMENTO */
  App.registrar("faturamento", async function () {
    App.carregando("#faturamento-cards");
    try {
      const dados = await App.buscar("modulo/faturamento");
      App.renderKpis("#faturamento-cards", dados.indicadores);

      const funil = (dados.funil || []).filter((e) => e.valor !== null && e.valor !== undefined);
      G.funil("graf-faturamento-funil", funil.map((e) => e.etapa), funil.map((e) => e.valor));

      const situacao = ranking(dados.por_situacao, "situacao");
      G.rosca("graf-faturamento-situacao", situacao.rotulos, situacao.valores);

      const mensal = serieMensal(dados.evolucao_faturado);
      G.barras("graf-faturamento-mensal", mensal.rotulos, mensal.valores, { nome: "Faturado" });

      const cidade = ranking(dados.por_cidade, "cidade");
      G.barrasHorizontais("graf-faturamento-cidade", cidade.rotulos, cidade.valores);

      App.tabela("#faturamento-tabela", [
        { chave: "cidade", titulo: "Cidade", clique: "cidade" },
        { chave: "total", titulo: "Termos", tipo: "numero" },
        { chave: "participacao", titulo: "Participação", tipo: "percentual" },
      ], dados.por_cidade);
    } catch (e) {
      erro("#faturamento-cards", e.message);
    }
  });

  /* ---------------------------------------------------------------- VENDAS */
  App.registrar("vendas", async function () {
    App.carregando("#vendas-cards");
    try {
      const dados = await App.buscar("modulo/vendas");
      periodoTexto(dados, "#vendas-periodo");
      document.getElementById("vendas-bloco").innerHTML = App.blocoMeta(dados.bloco_principal);
      App.renderKpis("#vendas-cards", dados.indicadores);
      matrizMeta("#vendas-matriz", dados.blocos_meta);

      const mensal = serieMensal(dados.evolucao_mensal);
      G.barras("graf-vendas-mensal", mensal.rotulos, mensal.valores, { nome: "Venda" });

      const diario = serieDiaria(dados.evolucao_diaria);
      G.diarioAcumulado("graf-vendas-diario", diario.datas, diario.diario, diario.acumulado, null);

      const frente = ranking(dados.por_frente, "frente");
      G.rosca("graf-vendas-frente", frente.rotulos, frente.valores);

      const cidade = ranking(dados.por_cidade, "cidade");
      G.barrasHorizontais("graf-vendas-cidade", cidade.rotulos, cidade.valores);

      App.tabela("#vendas-top-cidades", [
        { chave: "cidade", titulo: "Cidade", clique: "cidade" },
        { chave: "total", titulo: "Vendas", tipo: "numero" },
        { chave: "participacao", titulo: "Part.", tipo: "percentual" },
      ], dados.top_cidades);

      App.tabela("#vendas-top-equipes", [
        { chave: "equipe", titulo: "Equipe", clique: "equipe" },
        { chave: "total", titulo: "Vendas", tipo: "numero" },
        { chave: "participacao", titulo: "Part.", tipo: "percentual" },
      ], dados.top_equipes);
    } catch (e) {
      erro("#vendas-cards", e.message);
    }
  });

  /* ----------------------------------------------------------- IMPLANTAÇÃO */
  App.registrar("implantacao", async function () {
    App.carregando("#implantacao-cards");
    try {
      const dados = await App.buscar("modulo/implantacao");
      periodoTexto(dados, "#implantacao-periodo");

      const f = dados.faturamento || {};
      document.getElementById("implantacao-alerta").innerHTML = f.alerta
        ? `<div class="aviso aviso--atencao"><span>⚠</span><div>${App.escapar(f.alerta)}</div></div>` : "";

      matrizMeta("#implantacao-matriz", dados.blocos_meta);
      document.getElementById("implantacao-bloco").innerHTML = App.blocoMeta(dados.bloco_principal);
      App.renderKpis("#implantacao-cards", dados.indicadores);

      document.getElementById("implantacao-faturamento").innerHTML = [
        App.miniInfo("Quantidade faturada", App.numero(f.quantidade_faturada)),
        App.miniInfo("Quantidade não faturada", App.numero(f.quantidade_nao_faturada)),
        App.miniInfo("Valor faturado", f.valor_faturado === null || f.valor_faturado === undefined
          ? "Não informado" : App.moeda(f.valor_faturado)),
        App.miniInfo("% faturado", App.percentual(f.percentual_faturado)),
        App.miniInfo("% não faturado", App.percentual(f.percentual_nao_faturado)),
      ].join("");

      G.rosca("graf-implantacao-faturado",
        ["Faturada", "Não faturada"],
        [f.quantidade_faturada || 0, f.quantidade_nao_faturada || 0]);

      const pendentes = ranking(dados.nao_faturadas_por_cidade, "cidade");
      G.barrasHorizontais("graf-implantacao-pendente", pendentes.rotulos, pendentes.valores,
        { cor: "#c62828" });

      const servicos = serieMensal(dados.evolucao_servicos);
      const vcg = serieMensal(dados.evolucao_vcg);
      const geral = serieMensal(dados.evolucao_mensal);
      const mapa = (serie) => {
        const m = {};
        serie.rotulos.forEach((r, i) => { m[r] = serie.valores[i]; });
        return m;
      };
      const mServicos = mapa(servicos);
      const mVcg = mapa(vcg);
      G.agrupado("graf-implantacao-mensal", geral.rotulos, [
        { nome: "Serviços", valores: geral.rotulos.map((r) => mServicos[r] || 0) },
        { nome: "VCG", valores: geral.rotulos.map((r) => mVcg[r] || 0) },
      ]);

      const diario = serieDiaria(dados.evolucao_diaria);
      G.diarioAcumulado("graf-implantacao-diario", diario.datas, diario.diario, diario.acumulado, null);

      const cidade = ranking(dados.por_cidade, "cidade");
      G.barrasHorizontais("graf-implantacao-cidade", cidade.rotulos, cidade.valores);

      const equipe = ranking(dados.por_equipe, "equipe");
      G.barrasHorizontais("graf-implantacao-equipe", equipe.rotulos, equipe.valores);
    } catch (e) {
      erro("#implantacao-cards", e.message);
    }
  });

  /* ----------------------------------------------------------- PROGRAMAÇÃO */
  App.registrar("programacao", async function () {
    App.carregando("#programacao-cards");
    try {
      const dados = await App.buscar("modulo/programacao");
      const alvoData = document.getElementById("programacao-data");
      if (alvoData) alvoData.textContent = dados.data_referencia_br || dados.periodo.rotulo;

      App.renderKpis("#programacao-cards", dados.indicadores);

      const seletor = document.getElementById("programacao-seletor-data");
      if (seletor && !seletor.dataset.pronto) {
        seletor.innerHTML = (dados.datas_disponiveis || []).map((d) => {
          const partes = d.split("-");
          return `<option value="${d}">${partes[2]}/${partes[1]}/${partes[0]}</option>`;
        }).join("");
        seletor.value = dados.data_referencia || "";
        seletor.dataset.pronto = "1";
        seletor.addEventListener("change", () => {
          App.estado.filtros.data_fim = seletor.value;
          App.estado.filtros.data_inicio = seletor.value;
          App.atualizarUrl();
          App.sincronizarFormulario();
          App.recarregarPagina();
        });
      }

      App.tabela("#programacao-agenda", [
        { chave: "data", titulo: "Data" },
        { chave: "regiao", titulo: "Região", clique: "regiao" },
        { chave: "equipe", titulo: "Equipe", clique: "equipe" },
        { chave: "projeto", titulo: "Projeto", clique: "projeto" },
        { chave: "cidade", titulo: "Cidade", clique: "cidade" },
        { chave: "qtd_os", titulo: "O.S.", tipo: "numero" },
      ], dados.agenda, { vazio: "Sem programação para a data selecionada." });

      const desequilibrios = dados.desequilibrios || [];
      document.getElementById("programacao-desequilibrios").innerHTML = desequilibrios.length
        ? desequilibrios.map((d) => `
            <div class="insight insight--${d.tipo === "sobrecarregada" ? "alerta" : "info"}">
              <span class="insight__icone">${d.tipo === "sobrecarregada" ? "▲" : "▼"}</span>
              <div>${App.escapar(d.texto)}</div>
            </div>`).join("")
        : `<div class="vazio">Carga equilibrada entre as equipes programadas.</div>`;

      const equipe = ranking(dados.por_equipe, "equipe");
      G.barrasHorizontais("graf-programacao-equipe", equipe.rotulos, equipe.valores);
      const regiao = ranking(dados.por_regiao, "regiao");
      G.barras("graf-programacao-regiao", regiao.rotulos, regiao.valores, { mostrarValores: true });
      const projeto = ranking(dados.por_projeto, "projeto");
      G.barrasHorizontais("graf-programacao-projeto", projeto.rotulos, projeto.valores);

      const dia = serieDiaria(dados.por_dia);
      G.barras("graf-programacao-dia", dia.datas, dia.diario, { nome: "O.S." });
    } catch (e) {
      erro("#programacao-cards", e.message);
    }
  });

  /* --------------------------------------------------------------- EQUIPES */
  App.registrar("equipes", async function () {
    App.carregando("#equipes-cards");
    const seletor = document.getElementById("equipes-base");
    const base = seletor ? seletor.value : "implantacao";
    try {
      const dados = await App.buscar("modulo/equipes", { base });
      App.renderKpis("#equipes-cards", dados.indicadores);

      App.tabela("#equipes-tabela", [
        { chave: "equipe", titulo: "Equipe", clique: "equipe" },
        { chave: "frente", titulo: "Frente", clique: "frente" },
        { chave: "termos", titulo: "Termos", tipo: "numero" },
        { chave: "vendas", titulo: "Venda", tipo: "numero" },
        { chave: "implantacao", titulo: "Implantação", tipo: "numero" },
        { chave: "meta", titulo: "Meta", tipo: "numero", vazio: "Não cadastrada" },
        { chave: "atingimento", titulo: "% Meta", tipo: "percentual" },
        { chave: "media_dia", titulo: "Média/Dia", tipo: "numero", casas: 1 },
        { chave: "status", titulo: "Status", tipo: "status" },
      ], dados.tabela, { vazio: "Nenhuma equipe com produção no período." });

      const r = ranking(dados.ranking, "equipe");
      G.barrasHorizontais("graf-equipes-ranking", r.rotulos, r.valores);
      const diaria = serieDiaria(dados.producao_diaria);
      G.diarioAcumulado("graf-equipes-diaria", diaria.datas, diaria.diario, diaria.acumulado, null);

      if (seletor && !seletor.dataset.pronto) {
        seletor.dataset.pronto = "1";
        seletor.addEventListener("change", () => App.recarregarPagina());
      }
    } catch (e) {
      erro("#equipes-cards", e.message);
    }
  });

  /* --------------------------------------------------------------- CIDADES */
  App.registrar("cidades", async function () {
    App.carregando("#cidades-tabela");
    try {
      const dados = await App.buscar("modulo/cidades");
      periodoTexto(dados, "#cidades-periodo");

      App.tabela("#cidades-tabela", [
        { chave: "cidade", titulo: "Cidade", clique: "cidade" },
        { chave: "termos", titulo: "Termos", tipo: "numero" },
        { chave: "vendas", titulo: "Venda", tipo: "numero" },
        { chave: "implantacao", titulo: "Implantação", tipo: "numero" },
        { chave: "faturamento", titulo: "Faturamento", tipo: "numero" },
        { chave: "meta", titulo: "Meta", tipo: "numero", vazio: "Não cadastrada" },
        { chave: "atingimento", titulo: "% Meta", tipo: "percentual" },
        { chave: "status", titulo: "Status", tipo: "status" },
      ], dados.tabela, { vazio: "Nenhuma cidade com movimento no período." });

      const venda = ranking(dados.maior_venda, "cidade");
      G.barrasHorizontais("graf-cidades-venda", venda.rotulos, venda.valores);
      const impl = ranking(dados.maior_implantacao, "cidade");
      G.barrasHorizontais("graf-cidades-implantacao", impl.rotulos, impl.valores);
      const fat = ranking(dados.maior_faturamento, "cidade");
      G.barrasHorizontais("graf-cidades-faturamento", fat.rotulos, fat.valores, { cor: "#128a52" });

      App.tabela("#cidades-abaixo", [
        { chave: "cidade", titulo: "Cidade", clique: "cidade" },
        { chave: "implantacao", titulo: "Realizado", tipo: "numero" },
        { chave: "meta", titulo: "Meta", tipo: "numero" },
        { chave: "atingimento", titulo: "% Meta", tipo: "percentual" },
        { chave: "status", titulo: "Status", tipo: "status" },
      ], dados.abaixo_da_meta, { vazio: "Nenhuma cidade abaixo da meta (ou sem metas cadastradas)." });
    } catch (e) {
      erro("#cidades-tabela", e.message);
    }
  });

  /* ----------------------------------------------------------------- METAS */
  App.registrar("metas", async function () {
    App.carregando("#metas-acompanhamento");
    try {
      const dados = await App.buscar("metas");
      periodoTexto(dados, "#metas-periodo");

      document.getElementById("metas-aviso").innerHTML = dados.tem_metas ? "" :
        `<div class="aviso aviso--atencao"><span>⚠</span><div>
          <strong>Nenhuma meta cadastrada.</strong> Envie a planilha de metas em
          Atualização de Dados. O sistema não estima metas.</div></div>`;

      App.tabela("#metas-acompanhamento", [
        { chave: "modulo", titulo: "Módulo" },
        { chave: "meta", titulo: "Meta", tipo: "numero", vazio: "Não cadastrada" },
        { chave: "meta_acumulada", titulo: "Meta até hoje", tipo: "numero" },
        { chave: "realizado", titulo: "Realizado", tipo: "numero" },
        { chave: "falta", titulo: "Falta", tipo: "numero" },
        { chave: "atingimento", titulo: "% Meta", tipo: "percentual" },
        { chave: "media_dia", titulo: "Média/Dia", tipo: "numero", casas: 1 },
        { chave: "necessario_por_dia", titulo: "Necessário/Dia", tipo: "numero", casas: 1 },
        { chave: "projecao", titulo: "Projeção", tipo: "numero" },
        { chave: "status", titulo: "Status", tipo: "status" },
      ], dados.acompanhamento);

      document.getElementById("metas-blocos").innerHTML = dados.acompanhamento.map((b) => `
        <div class="painel"><div class="painel__cabecalho">
          <div class="painel__titulo">${App.escapar(b.modulo)}</div>
          <span class="selo selo--${b.status}">${b.atingimento === null ? "Sem meta"
            : App.percentual(b.atingimento)}</span>
        </div><div class="painel__corpo">${App.blocoMeta(b)}</div></div>`).join("");

      App.tabela("#metas-tabela", [
        { chave: "ano", titulo: "Ano" },
        { chave: "mes", titulo: "Mês" },
        { chave: "modulo", titulo: "Módulo" },
        { chave: "segmento", titulo: "Segmento" },
        { chave: "cidade", titulo: "Cidade" },
        { chave: "equipe", titulo: "Equipe" },
        { chave: "valor_meta", titulo: "Meta", tipo: "numero" },
      ], dados.cadastradas, { vazio: "Nenhuma meta cadastrada para o ano selecionado." });
    } catch (e) {
      erro("#metas-acompanhamento", e.message);
    }
  });

  /* -------------------------------------------------------------- ANÁLISES */
  App.registrar("analises", async function () {
    App.carregando("#analises-insights");
    try {
      const [insights, home] = await Promise.all([
        App.buscar("insights"), App.buscar("home"),
      ]);
      periodoTexto(insights, "#analises-periodo");

      const icones = { positivo: "▲", alerta: "▼", info: "•" };
      document.getElementById("analises-insights").innerHTML = insights.insights.length
        ? insights.insights.map((i) => `
            <div class="insight insight--${i.tipo}">
              <span class="insight__icone">${icones[i.tipo] || "•"}</span>
              <div>${App.escapar(i.texto)}
                <span class="painel__descricao">origem: ${App.escapar(i.origem)}</span></div>
            </div>`).join("")
        : `<div class="vazio">Sem insights: não há dados suficientes no período.</div>`;

      App.tabela("#analises-comparacao", [
        { chave: "titulo", titulo: "Indicador" },
        { chave: "texto", titulo: "Atual" },
        { chave: "anterior", titulo: "Anterior", tipo: "numero" },
        { chave: "texto_variacao", titulo: "Variação" },
      ], home.cards.filter((c) => c.anterior !== null && c.anterior !== undefined),
        { vazio: "Sem base de comparação com o período anterior." });

      App.tabela("#analises-projecao", [
        { chave: "rotulo", titulo: "Módulo" },
        { chave: "realizado", titulo: "Realizado", tipo: "numero" },
        { chave: "projecao", titulo: "Projeção", tipo: "numero" },
        { chave: "meta", titulo: "Meta", tipo: "numero", vazio: "Não cadastrada" },
        { chave: "status", titulo: "Status", tipo: "status" },
      ], home.modulos);

      const meses = {};
      Object.values(home.evolucao).forEach((lista) =>
        (lista || []).forEach((r) => { meses[r.ano_mes] = r.rotulo; }));
      const chaves = Object.keys(meses).sort();
      const linha = (lista) => {
        const mapa = {};
        (lista || []).forEach((r) => { mapa[r.ano_mes] = r.total; });
        return chaves.map((k) => (k in mapa ? mapa[k] : null));
      };
      G.linhas("graf-analises-evolucao", chaves.map((k) => meses[k]), [
        { nome: "Termos", valores: linha(home.evolucao.termos) },
        { nome: "Venda", valores: linha(home.evolucao.vendas) },
        { nome: "Implantação", valores: linha(home.evolucao.implantacao) },
      ]);
    } catch (e) {
      erro("#analises-insights", e.message);
    }
  });

  /* --------------------------------------------------------------- ALERTAS */
  App.registrar("alertas", async function () {
    App.carregando("#alertas-lista");
    try {
      const dados = await App.buscar("alertas");
      periodoTexto(dados, "#alertas-periodo");

      const r = dados.resumo;
      document.getElementById("alertas-resumo").innerHTML = `
        <div class="card card--vermelho"><div class="card__faixa"></div>
          <div class="card__titulo">🔴 Críticos</div><div class="card__valor">${r.criticos}</div>
          <div class="card__explicacao">Necessitam intervenção imediata</div></div>
        <div class="card card--amarelo"><div class="card__faixa"></div>
          <div class="card__titulo">🟡 Atenção</div><div class="card__valor">${r.atencao}</div>
          <div class="card__explicacao">Risco de não atingir a meta</div></div>
        <div class="card card--verde"><div class="card__faixa"></div>
          <div class="card__titulo">🟢 Normais</div><div class="card__valor">${r.normais}</div>
          <div class="card__explicacao">Desempenho adequado</div></div>`;

      const desenhar = (categoria) => {
        const lista = categoria ? dados.alertas.filter((a) => a.categoria === categoria)
          : dados.alertas;
        document.getElementById("alertas-lista").innerHTML = lista.length
          ? lista.map((a) => `
              <div class="alerta-item alerta-item--${a.categoria}">
                <span style="font-size:16px">${a.icone}</span>
                <div><div class="alerta-item__titulo">${App.escapar(a.titulo)}</div>
                  <div class="alerta-item__descricao">${App.escapar(a.descricao)}</div></div>
              </div>`).join("")
          : `<div class="vazio">Nenhum alerta nesta categoria.</div>`;
      };
      desenhar("");

      document.querySelectorAll("[data-categoria]").forEach((aba) => {
        aba.addEventListener("click", () => {
          document.querySelectorAll("[data-categoria]").forEach((o) => o.classList.remove("ativa"));
          aba.classList.add("ativa");
          desenhar(aba.dataset.categoria);
        });
      });
    } catch (e) {
      erro("#alertas-lista", e.message);
    }
  });

  /* ---------------------------------------------------------- ATUALIZAÇÃO */
  const TIPOS_BASE = [
    ["", "Detectar automaticamente"], ["termos", "Termos Aplicados"],
    ["faturamento", "Faturamento de Termos"], ["vendas", "Venda"],
    ["implantacao", "Implantação"], ["programacao", "Programação Diária"],
    ["metas", "Metas"],
  ];

  App.registrar("atualizacao", async function () {
    const area = document.getElementById("area-upload");
    const input = document.getElementById("input-arquivos");
    const lista = document.getElementById("lista-arquivos");
    const botao = document.getElementById("btn-atualizar");
    if (!area || area.dataset.pronto) { await carregarHistorico(); return; }
    area.dataset.pronto = "1";

    let arquivos = [];

    function desenharLista() {
      lista.innerHTML = arquivos.map((arquivo, indice) => `
        <div class="arquivo-linha">
          <span>▤</span>
          <div class="arquivo-linha__nome">${App.escapar(arquivo.name)}
            <div class="arquivo-linha__tamanho">${(arquivo.size / 1024).toFixed(0)} KB</div></div>
          <select data-indice="${indice}">
            ${TIPOS_BASE.map(([v, t]) => `<option value="${v}">${t}</option>`).join("")}
          </select>
          <button class="btn" data-remover="${indice}">✕</button>
        </div>`).join("");
      botao.disabled = arquivos.length === 0;
      lista.querySelectorAll("[data-remover]").forEach((b) => {
        b.addEventListener("click", () => {
          arquivos.splice(Number(b.dataset.remover), 1);
          desenharLista();
        });
      });
    }

    function adicionar(novos) {
      Array.from(novos).forEach((arquivo) => {
        if (!arquivos.some((a) => a.name === arquivo.name && a.size === arquivo.size)) {
          arquivos.push(arquivo);
        }
      });
      desenharLista();
    }

    area.addEventListener("click", () => input.click());
    input.addEventListener("change", () => { adicionar(input.files); input.value = ""; });
    ["dragenter", "dragover"].forEach((evento) =>
      area.addEventListener(evento, (e) => { e.preventDefault(); area.classList.add("arrastando"); }));
    ["dragleave", "drop"].forEach((evento) =>
      area.addEventListener(evento, (e) => { e.preventDefault(); area.classList.remove("arrastando"); }));
    area.addEventListener("drop", (e) => adicionar(e.dataTransfer.files));

    botao.addEventListener("click", async () => {
      if (!arquivos.length) return;
      const etapas = await App.api("/api/etapas");
      const caixaEtapas = document.getElementById("etapas-processo");
      const barra = document.getElementById("barra-upload");
      document.getElementById("progresso-upload").hidden = false;
      caixaEtapas.hidden = false;
      botao.disabled = true;
      botao.textContent = "ATUALIZANDO...";

      const render = (indice) => {
        caixaEtapas.innerHTML = etapas.etapas.map((etapa, i) => `
          <div class="etapa ${i < indice ? "concluida" : (i === indice ? "ativa" : "")}">
            <span class="etapa__bolha">${i < indice ? "✓" : i + 1}</span>
            <span>${App.escapar(etapa)}${i === indice ? "..." : ""}</span>
          </div>`).join("");
        barra.style.width = `${Math.round(((indice + 1) / etapas.etapas.length) * 100)}%`;
      };

      let etapaAtual = 0;
      render(0);
      const relogio = setInterval(() => {
        if (etapaAtual < etapas.etapas.length - 2) render(++etapaAtual);
      }, 700);

      const formulario = new FormData();
      arquivos.forEach((arquivo) => formulario.append("arquivos", arquivo));
      lista.querySelectorAll("select[data-indice]").forEach((select) =>
        formulario.append("tipo", select.value));

      try {
        const resposta = await fetch("/api/upload", { method: "POST", body: formulario });
        const dados = await resposta.json();
        clearInterval(relogio);
        render(etapas.etapas.length - 1);
        barra.style.width = "100%";
        mostrarResultado(dados);
        if (dados.ok) {
          App.toast(dados.mensagem, "sucesso", "Dashboard atualizado");
          arquivos = [];
          desenharLista();
          const topo = document.getElementById("topo-ultima-atualizacao");
          if (topo && dados.status) topo.textContent = dados.status.ultima_atualizacao || "-";
        } else {
          App.toast(dados.mensagem || "Nenhum arquivo importado.", "erro", "Atenção");
        }
        await carregarHistorico();
      } catch (e) {
        clearInterval(relogio);
        App.toast("Falha de comunicação com o servidor.", "erro");
      } finally {
        botao.disabled = arquivos.length === 0;
        botao.textContent = "ATUALIZAR DASHBOARD";
      }
    });

    await carregarHistorico();
  });

  function mostrarResultado(dados) {
    const alvo = document.getElementById("resultado-upload");
    if (!alvo) return;
    const cores = { SUCESSO: "verde", ATENCAO: "amarelo", ERRO: "vermelho" };
    alvo.innerHTML = `<div style="margin-bottom:12px"><strong>${App.escapar(dados.mensagem || "")}</strong></div>` +
      (dados.resultados || []).map((r) => `
        <div class="alerta-item alerta-item--${r.status === "ERRO" ? "CRITICO"
          : (r.status === "ATENCAO" ? "ATENCAO" : "NORMAL")}">
          <span class="selo selo--${cores[r.status] || "cinza"}">${r.status}</span>
          <div>
            <div class="alerta-item__titulo">${App.escapar(r.arquivo)}
              ${r.titulo_dataset ? `— ${App.escapar(r.titulo_dataset)}` : ""}</div>
            <div class="alerta-item__descricao">${App.escapar(r.mensagem)}</div>
            ${(r.detalhes || []).length ? `<ul class="alerta-item__descricao" style="margin:6px 0 0 16px">
              ${r.detalhes.map((d) => `<li>${App.escapar(d)}</li>`).join("")}</ul>` : ""}
          </div>
        </div>`).join("");
  }

  async function carregarHistorico() {
    try {
      const dados = await App.api("/api/historico?limite=50");
      App.tabela("#historico-tabela", [
        { chave: "data_hora", titulo: "Data/Hora" },
        { chave: "arquivo", titulo: "Arquivo" },
        { chave: "dataset", titulo: "Base" },
        { chave: "registros_lidos", titulo: "Lidos", tipo: "numero" },
        { chave: "registros_inseridos", titulo: "Novos", tipo: "numero" },
        { chave: "registros_atualizados", titulo: "Atualizados", tipo: "numero" },
        { chave: "registros_ignorados", titulo: "Descartados", tipo: "numero" },
        { chave: "status", titulo: "Status" },
        { chave: "usuario", titulo: "Usuário" },
      ], dados.registros, { vazio: "Nenhuma atualização registrada." });
    } catch (e) {
      App.vazio("#historico-tabela", "Não foi possível carregar o histórico.");
    }
  }

  /* --------------------------------------------------------- CONFIGURAÇÕES */
  App.registrar("configuracoes", async function () {
    try {
      const [config, status, datasets] = await Promise.all([
        App.api("/api/configuracoes"), App.api("/api/status"), App.api("/api/datasets"),
      ]);
      const formulario = document.getElementById("form-configuracoes");
      Object.entries(config.configuracoes).forEach(([chave, valor]) => {
        if (formulario.elements[chave]) formulario.elements[chave].value = valor;
      });

      if (!formulario.dataset.pronto) {
        formulario.dataset.pronto = "1";
        formulario.addEventListener("submit", async (evento) => {
          evento.preventDefault();
          const dados = Object.fromEntries(new FormData(formulario).entries());
          try {
            await App.api("/api/configuracoes", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(dados),
            });
            App.aplicarTema(dados.tema);
            App.toast("Preferências salvas.", "sucesso");
          } catch (e) {
            App.toast(e.message, "erro");
          }
        });
      }

      App.tabela("#configuracoes-sistema", [
        { chave: "item", titulo: "Item" }, { chave: "valor", titulo: "Valor" },
      ], [
        { item: "Aplicação", valor: status.aplicacao },
        { item: "Versão", valor: status.versao },
        { item: "Dados importados", valor: status.tem_dados ? "Sim" : "Não" },
        { item: "Metas cadastradas", valor: status.metas_cadastradas ? "Sim" : "Não" },
        { item: "Última atualização", valor: status.ultima_atualizacao || "Nenhuma" },
        { item: "Itens em cache", valor: String(status.cache.itens) },
        { item: "TTL do cache (s)", valor: String(status.cache.ttl_segundos) },
      ]);

      App.tabela("#configuracoes-datasets", [
        { chave: "titulo", titulo: "Base" }, { chave: "modulo", titulo: "Módulo" },
        { chave: "tabela", titulo: "Tabela" }, { chave: "obrigatorias", titulo: "Colunas obrigatórias" },
        { chave: "chave", titulo: "Chave única (evita duplicidade)" },
      ], datasets.datasets.map((d) => ({
        titulo: d.titulo, modulo: d.modulo, tabela: d.tabela,
        obrigatorias: d.campos.filter((c) => c.obrigatorio).map((c) => c.nome).join(", "),
        chave: d.chave_unica.join(" + "),
      })));
    } catch (e) {
      App.toast(e.message, "erro");
    }
  });

  /* ------------------------------------------------------------ DICIONÁRIO */
  App.registrar("dicionario", async function () {
    const alvo = document.getElementById("dicionario-conteudo");
    App.carregando("#dicionario-conteudo");
    try {
      const dados = await App.api("/api/datasets");
      alvo.innerHTML = dados.datasets.map((d) => `
        <div class="painel" style="margin-bottom:16px">
          <div class="painel__cabecalho">
            <div><div class="painel__titulo">${App.escapar(d.titulo)}
              <span class="selo selo--azul">${App.escapar(d.modulo)}</span></div>
              <div class="painel__descricao">${App.escapar(d.descricao)}</div>
              <div class="painel__descricao">Tabela: <code>${App.escapar(d.tabela)}</code> ·
                Chave única: <code>${App.escapar(d.chave_unica.join(" + "))}</code></div></div>
          </div>
          <div class="painel__corpo painel__corpo--limpo">
            <div class="tabela-wrap"><table class="tabela"><thead><tr>
              <th>Coluna interna</th><th>Tipo</th><th>Obrigatória</th>
              <th>Descrição</th><th>Cabeçalhos aceitos na planilha</th>
            </tr></thead><tbody>
            ${d.campos.map((c) => `<tr>
              <td><code>${App.escapar(c.nome)}</code></td>
              <td>${App.escapar(c.tipo)}</td>
              <td>${c.obrigatorio ? '<span class="selo selo--vermelho">Sim</span>'
                : '<span class="selo selo--cinza">Não</span>'}</td>
              <td>${App.escapar(c.descricao)}</td>
              <td class="painel__descricao">${App.escapar([c.nome].concat(c.aliases).join(" · "))}</td>
            </tr>`).join("")}
            </tbody></table></div>
          </div>
        </div>`).join("");
    } catch (e) {
      erro("#dicionario-conteudo", e.message);
    }
  });
})(window);
