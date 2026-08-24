/* =========================================================================
   Confere as regras do painel offline contra planilhas reais, sem navegador.

   Uso:
     node offline/conferir.js <planilha.xlsx> [mais planilhas...]

   Serve para validar um número antes de abrir o dashboard: as mesmas
   funções de regras.js são aplicadas aos mesmos arquivos.
   ========================================================================= */
"use strict";

const fs = require("fs");
const path = require("path");

const XLSX = require(path.join(__dirname, "xlsx.full.min.js"));
const Regras = require(path.join(__dirname, "regras.js")).Regras;

function lerArquivo(caminho) {
  const nome = path.basename(caminho);
  const wb = XLSX.read(fs.readFileSync(caminho), { type: "buffer", cellDates: true });
  const aba = wb.SheetNames.find((n) => Regras.N(n) === "PAGE 1") || wb.SheetNames[0];
  const matriz = XLSX.utils.sheet_to_json(wb.Sheets[aba], { header: 1, defval: "", raw: true });
  const lidas = Regras.registros(matriz);
  const linhas = [];
  lidas.linhas.forEach((linha) => {
    const registro = Regras.normalizar(linha, { nome, caminho });
    if (registro) linhas.push(registro);
  });
  return { nome, aba, cabecalho: lidas.cabecalho, lidas: lidas.linhas.length, linhas,
    motivo: lidas.motivo, cabecalhos: lidas.cabecalhos };
}

function main() {
  const arquivos = process.argv.slice(2);
  if (!arquivos.length) {
    console.error("Informe pelo menos uma planilha.");
    process.exit(2);
  }

  // Mesma seleção de cópias do painel: só arquivos da mesma pasta com o
  // mesmo nome-base são cópias um do outro.
  const falsos = arquivos.map((c) => ({
    name: path.basename(c), webkitRelativePath: c, lastModified: fs.statSync(c).mtimeMs, caminho: c,
  }));
  const escolhidos = Regras.selecionarCopias(falsos);

  let todas = [];
  console.log("AUDITORIA POR ARQUIVO");
  console.log("=".repeat(78));
  falsos.forEach((f) => {
    if (!escolhidos.has(f)) {
      console.log(`  ${f.name}: ignorado (cópia do mesmo arquivo)`);
      return;
    }
    const r = lerArquivo(f.caminho);
    const motivo = r.motivo ? `  [${r.motivo}: ${r.cabecalhos.join(", ")}]` : "";
    console.log(`  ${r.nome}: aba "${r.aba}", cabeçalho na linha ${r.cabecalho + 1}, `
      + `${r.lidas} lida(s), ${r.linhas.length} importada(s)${motivo}`);
    todas = todas.concat(r.linhas);
  });

  const meses = [...new Set(todas.map((r) => r.mes))].sort();
  console.log(`\nLinhas importadas: ${todas.length} | meses: ${meses.join(", ") || "-"}`);

  meses.forEach((mes) => {
    const doMes = todas.filter((r) => r.mes === mes);
    const imp = Regras.implantacoes(doMes);
    const serv = imp.filter((r) => r.frente === "SERVICOS");
    const vcg = imp.filter((r) => r.frente === "VCG");
    const vds = Regras.vendas(doMes);
    const tms = Regras.termos(doMes);
    const dias = Regras.diasUteis(doMes);
    const media = (n) => (n / dias).toFixed(1).replace(".", ",");

    console.log(`\n${"=".repeat(78)}\n${mes}  (${dias} dias úteis)\n${"=".repeat(78)}`);
    console.log(`  Implantação Geral ....... ${serv.length + vcg.length}`);
    console.log(`    Serviços .............. ${serv.length}   (${media(serv.length)}/dia)`);
    console.log(`    VCG ................... ${vcg.length}   (${media(vcg.length)}/dia)`);
    console.log(`  Venda total ............. ${vds.length}`);
    console.log(`    Comercial ............. ${vds.filter((r) => r.canal === "COMERCIAL").length}`);
    console.log(`    VCG ................... ${vds.filter((r) => r.canal === "VCG").length}`);
    console.log(`    Outros canais ......... ${vds.filter((r) => r.canal === "OUTROS").length}`);
    console.log(`  Termos aplicados ........ ${tms.length}`);
    console.log(`    Serviços .............. ${tms.filter((r) => r.frenteTermo === "SERVICOS").length}`);
    console.log(`    VCG ................... ${tms.filter((r) => r.frenteTermo === "VCG").length}`);
  });
}

main();
