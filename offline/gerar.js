/* =========================================================================
   Monta o dashboard.html a partir de dashboard.fonte.html.

   Uso:  node offline/gerar.js

   O painel é entregue como UM arquivo só: o leitor de planilhas e as regras
   de cálculo entram embutidos. Enquanto ficavam do lado de fora, bastava o
   usuário abrir o dashboard sem extrair o ZIP inteiro (ou o navegador ler o
   .js em outra codificação) para o painel quebrar no primeiro clique com
   "Cannot read properties of undefined".

   As regras continuam morando em regras.js, que é o que conferir.js e
   testar.js carregam. Este script só copia o arquivo para dentro do HTML;
   testar.js confere que a cópia embutida está em dia.
   ========================================================================= */
"use strict";

const fs = require("fs");
const path = require("path");

const PASTA = __dirname;
const FONTE = path.join(PASTA, "dashboard.fonte.html");
const SAIDA = path.join(PASTA, "dashboard.html");

const MARCAS = [
  { marca: "/* inserir:xlsx */", arquivo: "xlsx.full.min.js" },
  { marca: "/* inserir:regras */", arquivo: "regras.js" },
];

/**
 * Insere um .js dentro de um <script> do HTML.
 *
 * Um "</script>" no meio do código encerraria a tag antes da hora; o
 * navegador lê "<\/script>" como o mesmo texto, sem fechar a tag.
 */
function embutir(html, marca, codigo) {
  if (!html.includes(marca)) {
    throw new Error(`dashboard.fonte.html não tem a marca ${marca}`);
  }
  const seguro = codigo.split("</script").join("<\\/script");
  return html.split(marca).join(seguro);
}

/** O dashboard.html que os arquivos de hoje produzem. */
function montar() {
  let html = fs.readFileSync(FONTE, "utf8");
  MARCAS.forEach(({ marca, arquivo }) => {
    html = embutir(html, marca, fs.readFileSync(path.join(PASTA, arquivo), "utf8"));
  });
  return html;
}

function main() {
  const html = montar();
  fs.writeFileSync(SAIDA, html);
  const kb = (Buffer.byteLength(html) / 1024).toFixed(0);
  console.log(`dashboard.html gerado (${kb} KB, arquivo único).`);
}

module.exports = { montar, SAIDA };

if (require.main === module) main();
