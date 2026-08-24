/* =========================================================================
   Regras de negócio do painel offline.

   Ficam separadas da interface porque é o que se confere contra as
   planilhas reais — o arquivo é carregado tanto pelo dashboard.html quanto
   pelo conferidor de linha de comando.
   ========================================================================= */
(function (raiz) {
  "use strict";

  /**
   * Texto comparável: sem acento, sem espaço sobrando, em maiúsculas.
   *
   * A faixa dos acentos vai escrita com escapes (u0300 a u036f), nunca com
   * os sinais em si: lida em outra codificação que não UTF-8, a faixa fica
   * invertida e o arquivo inteiro deixa de carregar — foi o que derrubou o
   * painel. Todo o código aqui é ASCII pelo mesmo motivo, e testar.js
   * confere isso; só comentário leva acento.
   */
  const N = (v) => String(v ?? "")
    .normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toUpperCase();

  /** Cabeçalho comparável: só letras e números, para casar variações. */
  const H = (v) => N(v).replace(/[^A-Z0-9]/g, "");

  const EQUIPES_VCG = ["RIOVCGPOPIN", "RIOVCGEXTIN", "RIOVCGVENIN"];
  const ATIVIDADES_IMPLANTACAO = ["LIGACAO DE AGUA", "LIGACAO DE ESGOTO"];
  const CODIGOS_TERMO = ["110013", "210013", "310013", "310031", "310025"];
  const STATUS_TERMO = ["FINALIZADA", "ENCERRADA COM OCORRENCIA"];
  const CODIGO_TERMO_VCG = "310013";

  /** Valor de uma coluna, aceitando as variações de cabeçalho conhecidas. */
  function celula(linha, nomes) {
    const alvo = new Set(nomes.map(H));
    const chave = Object.keys(linha).find((c) => alvo.has(H(c)));
    return chave ? linha[chave] : "";
  }

  /** Data em serial do Excel, Date, dd/mm/aaaa ou ISO. */
  function data(valor) {
    if (valor instanceof Date && !isNaN(valor)) return valor;
    if (typeof valor === "number") return new Date(Date.UTC(1899, 11, 30) + valor * 86400000);
    const texto = String(valor ?? "").trim();
    if (/^\d{5}(?:[.,]\d+)?$/.test(texto)) {
      return new Date(Date.UTC(1899, 11, 30) + Number(texto.replace(",", ".")) * 86400000);
    }
    let m = texto.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
    if (m) {
      let ano = +m[3];
      if (ano < 100) ano += 2000;
      return new Date(Date.UTC(ano, +m[2] - 1, +m[1]));
    }
    m = texto.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
    if (m) return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
    const p = Date.parse(texto);
    return isNaN(p) ? null : new Date(p);
  }

  const mesDe = (d) => d.getUTCFullYear() + "-" + String(d.getUTCMonth() + 1).padStart(2, "0");
  const identidade = (v) => String(v ?? "").trim().replace(/\.0+$/, "");

  const ehVcg = (recurso) => EQUIPES_VCG.some((e) => recurso.includes(e));

  /* ------------------------------------------------- seleção de arquivos */

  /** Sufixo de cópia do Windows: "relatório (3).xlsx" -> 3. */
  const numeroDaCopia = (nome) => +(nome.match(/\((\d+)\)(?=\.[^.]+$)/) || [, 0])[1];

  /** Nome sem o sufixo de cópia e sem a extensão. */
  const nomeBase = (nome) => nome
    .replace(/\s*\(\d+\)(?=\.[^.]+$)/, "")
    .replace(/\.[^.]+$/, "");

  /**
   * Uma cópia de cada arquivo.
   *
   * Só são cópias os arquivos na MESMA subpasta cujo nome-base é igual,
   * variando apenas o sufixo (1), (2). Agrupar pela data do nome eliminaria
   * fontes distintas — Termos e Faturamento do mesmo dia são arquivos
   * diferentes, não cópias.
   */
  function selecionarCopias(arquivos) {
    const grupos = new Map();
    arquivos.forEach((arquivo) => {
      const caminho = arquivo.webkitRelativePath || arquivo.name;
      const pasta = caminho.split("/").slice(0, -1).join("/");
      const chave = pasta + "|" + H(nomeBase(arquivo.name));
      grupos.set(chave, [...(grupos.get(chave) || []), arquivo]);
    });
    const manter = new Set();
    grupos.forEach((lista) => {
      lista.sort((a, b) => numeroDaCopia(b.name) - numeroDaCopia(a.name)
        || (b.lastModified || 0) - (a.lastModified || 0));
      manter.add(lista[0]);
    });
    return manter;
  }

  /* --------------------------------------------------- leitura da planilha */

  const COLUNAS_DATA = new Set([
    "DATA", "DATADAATIVIDADE", "DATAATIVIDADE", "DTATIVIDADE",
    "DATAFINALIZACAO", "DATADEFINALIZACAO", "DATAEXECUCAO", "DATADAEXECUCAO",
  ]);

  /**
   * Acha a linha de cabeçalho nas 30 primeiras e devolve os registros.
   * Retorna também o diagnóstico, para a auditoria explicar o descarte.
   */
  function registros(matriz) {
    let melhor = -1;
    let pontos = -1;
    matriz.slice(0, 30).forEach((linha, i) => {
      const h = linha.map(H);
      const nota = (h.some((x) => COLUNAS_DATA.has(x)) ? 10 : 0)
        + (h.includes("STATUSDAATIVIDADE") ? 3 : 0)
        + (h.includes("TIPODEATIVIDADE") ? 3 : 0)
        + (h.includes("MATRICULA") ? 2 : 0);
      if (nota > pontos) { pontos = nota; melhor = i; }
    });
    if (melhor < 0 || pontos < 10) {
      const cabecalhos = (matriz[0] || []).map((x) => String(x ?? "").trim())
        .filter(Boolean).slice(0, 12);
      return { linhas: [], cabecalho: -1, cabecalhos, motivo: "Sem coluna de data reconhecida" };
    }
    const vistos = new Map();
    const cabecalhos = matriz[melhor].map((x, i) => String(x ?? "").trim() || "COLUNA_" + (i + 1))
      .map((h) => {
        const n = (vistos.get(h) || 0) + 1;
        vistos.set(h, n);
        return n === 1 ? h : h + "_" + n;
      });
    const linhas = matriz.slice(melhor + 1)
      .filter((r) => r.some((x) => String(x ?? "").trim()))
      .map((r) => Object.fromEntries(cabecalhos.map((h, i) => [h, r[i] ?? ""])));
    return { linhas, cabecalho: melhor, cabecalhos, motivo: "" };
  }

  /** Converte uma linha da planilha no registro que o painel usa. */
  function normalizar(linha, origem) {
    const d = data(celula(linha, [
      "Data", "Data da Atividade", "Data Atividade", "Dt Atividade",
      "Data Finalizacao", "Data de Finalizacao", "Data Execucao", "Data da Execucao",
    ]));
    if (!d) return null;
    const recurso = N(celula(linha, ["Recurso", "Equipe"]));
    return {
      data: d,
      mes: mesDe(d),
      ano: String(d.getUTCFullYear()),
      matricula: identidade(celula(linha, ["Matricula"])),
      id: identidade(celula(linha, ["ID da Atividade", "Id Atividade", "ID"])),
      protocolo: identidade(celula(linha, [
        "Cod. Protocolo Origem", "Codigo Protocolo Origem", "Protocolo Origem",
        "P.O", "PO", "NUMERO_OS", "Numero OS",
      ])),
      status: N(celula(linha, ["Status da Atividade", "Status"])),
      atividade: N(celula(linha, ["Tipo de Atividade", "Atividade", "Servico"])),
      codigo: N(celula(linha, ["Codigo/Descricao"])),
      extras: N(celula(linha, ["Servico adicionais resposta"]))
        + " " + N(celula(linha, ["Servico posteriores resposta"])),
      recurso,
      frente: ehVcg(recurso) ? "VCG" : "SERVICOS",
      cidade: N(celula(linha, ["Cidade", "Municipio"])),
      arquivo: origem.nome,
      caminho: origem.caminho,
    };
  }

  /* ------------------------------------------------------------- medidas */

  /**
   * Implantações do recorte, uma por matrícula dentro do mês e da frente.
   *
   * É essa deduplicação que impede a produção de ser contada de novo a cada
   * arquivo diário em que a mesma ordem reaparece.
   */
  function implantacoes(linhas) {
    const unicas = new Map();
    linhas.forEach((r) => {
      if (r.status !== "FINALIZADA") return;
      if (!ATIVIDADES_IMPLANTACAO.includes(r.atividade)) return;
      const chave = r.matricula || r.protocolo || r.id;
      if (!chave) return;
      unicas.set(r.mes + "|" + r.frente + "|" + chave, r);
    });
    return [...unicas.values()];
  }

  /** Canal da venda, ou null quando a linha não é venda. */
  function canalDaVenda(r) {
    if (r.status !== "FINALIZADA") return null;
    const potencial = r.atividade === "VENDA POTENCIAIS/FACTIVEIS";
    const conhecido = ["113001", "313001", "114003", "118048"]
      .some((c) => r.codigo.includes(c));
    if (!potencial && !conhecido) return null;
    // 114003 e 118048 não somem: são Outros Canais.
    if (r.codigo.includes("114003") || r.codigo.includes("118048")) return "OUTROS";
    // O 113001 segue comercial mesmo quando a equipe é VCG.
    if (r.codigo.includes("113001")) return "COMERCIAL";
    if (r.frente === "VCG" && (potencial || r.codigo.includes("313001"))) return "VCG";
    return potencial ? "COMERCIAL" : null;
  }

  /** Vendas do recorte, deduplicadas pelo ID da Atividade. */
  function vendas(linhas) {
    const unicas = new Map();
    linhas.forEach((r) => {
      const canal = canalDaVenda(r);
      if (!canal) return;
      const id = r.id || r.protocolo
        || [r.data.toISOString().slice(0, 10), r.matricula, r.codigo, r.recurso].join("|");
      unicas.set(r.mes + "|" + canal + "|" + id, Object.assign({}, r, { canal }));
    });
    return [...unicas.values()];
  }

  /**
   * Frente do termo aplicado, ou null quando a linha não gera termo.
   *
   * Serviços aceita qualquer um dos códigos, desde que a equipe não seja
   * VCG. Em VCG só entra RIOVCGEXTIN com o 310013 — POPIN e VENIN ficam de
   * fora do realizado de Termos.
   */
  function frenteDoTermo(r) {
    if (!STATUS_TERMO.includes(r.status)) return null;
    const texto = r.codigo + " " + r.extras;
    const achados = CODIGOS_TERMO.filter((c) => texto.includes(c));
    if (!achados.length) return null;
    if (r.recurso.includes("RIOVCGEXTIN")) {
      return achados.includes(CODIGO_TERMO_VCG) ? "VCG" : null;
    }
    if (ehVcg(r.recurso)) return null;
    return "SERVICOS";
  }

  /** Termos aplicados, deduplicados pelo ID da Atividade. */
  function termos(linhas) {
    const unicos = new Map();
    linhas.forEach((r) => {
      const frente = frenteDoTermo(r);
      if (!frente) return;
      const id = r.id || r.protocolo || [r.mes, r.matricula, r.codigo].join("|");
      unicos.set(frente + "|" + id, Object.assign({}, r, {
        frenteTermo: frente, statusDerivado: "Termos Aplicados",
      }));
    });
    return [...unicos.values()];
  }

  /** Dias úteis decorridos: do dia 1 até o último dia com movimento. */
  function diasUteis(linhas) {
    const ultimoDia = new Map();
    linhas.forEach((r) => {
      ultimoDia.set(r.mes, Math.max(ultimoDia.get(r.mes) || 0, r.data.getUTCDate()));
    });
    let total = 0;
    ultimoDia.forEach((ultimo, mes) => {
      const [ano, m] = mes.split("-").map(Number);
      for (let dia = 1; dia <= ultimo; dia++) {
        const semana = new Date(Date.UTC(ano, m - 1, dia)).getUTCDay();
        if (semana !== 0 && semana !== 6) total++;
      }
    });
    return Math.max(total, 1);
  }

  raiz.Regras = {
    N, H, celula, data, mesDe, ehVcg,
    EQUIPES_VCG, ATIVIDADES_IMPLANTACAO, CODIGOS_TERMO, STATUS_TERMO,
    nomeBase, numeroDaCopia, selecionarCopias,
    registros, normalizar,
    implantacoes, canalDaVenda, vendas, frenteDoTermo, termos, diasUteis,
  };
})(typeof module !== "undefined" && module.exports ? module.exports : window);
