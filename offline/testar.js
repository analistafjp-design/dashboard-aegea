/* =========================================================================
   Validações obrigatórias do painel offline (seção 11 da especificação).

   Uso:  node offline/testar.js
   ========================================================================= */
"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const Regras = require(path.join(__dirname, "regras.js")).Regras;

let passou = 0;
function caso(nome, fn) {
  try {
    fn();
    passou++;
    console.log("  ok   " + nome);
  } catch (erro) {
    console.log("  FALHA " + nome + "\n       " + erro.message);
    process.exitCode = 1;
  }
}

/** Linha já normalizada, como sai de Regras.normalizar. */
function linha(campos) {
  const data = campos.data || new Date(Date.UTC(2026, 7, 10));
  const recurso = Regras.N(campos.recurso || "RIOMLTIN-001");
  return Object.assign({
    data,
    mes: Regras.mesDe(data),
    ano: String(data.getUTCFullYear()),
    matricula: "1", id: "", protocolo: "",
    status: "FINALIZADA",
    atividade: "LIGACAO DE AGUA",
    codigo: "", extras: "",
    recurso,
    frente: Regras.ehVcg(recurso) ? "VCG" : "SERVICOS",
    cidade: "MARICA", arquivo: "x.xlsx", caminho: "Interior/x.xlsx",
  }, campos, { recurso, frente: Regras.ehVcg(recurso) ? "VCG" : "SERVICOS" });
}

const arquivo = (name, dir, lastModified) => ({
  name, webkitRelativePath: dir + "/" + name, lastModified: lastModified || 1,
});

console.log("IMPLANTAÇÃO");
caso("Ligação de Água e de Esgoto contam", () => {
  const r = Regras.implantacoes([
    linha({ matricula: "1", atividade: "LIGACAO DE AGUA" }),
    linha({ matricula: "2", atividade: "LIGACAO DE ESGOTO" }),
    linha({ matricula: "3", atividade: "VISTORIA" }),
  ]);
  assert.strictEqual(r.length, 2);
});

caso("só status Finalizada conta", () => {
  const r = Regras.implantacoes([
    linha({ matricula: "1" }),
    linha({ matricula: "2", status: "EM EXECUCAO" }),
  ]);
  assert.strictEqual(r.length, 1);
});

caso("a mesma atividade repetida em arquivos diários conta uma vez", () => {
  const r = Regras.implantacoes([
    linha({ matricula: "9", data: new Date(Date.UTC(2026, 7, 21)), arquivo: "dia21.xlsx" }),
    linha({ matricula: "9", data: new Date(Date.UTC(2026, 7, 23)), arquivo: "dia23.xlsx" }),
  ]);
  assert.strictEqual(r.length, 1);
});

caso("a mesma matrícula em meses diferentes conta nos dois", () => {
  const r = Regras.implantacoes([
    linha({ matricula: "9", data: new Date(Date.UTC(2026, 6, 10)) }),
    linha({ matricula: "9", data: new Date(Date.UTC(2026, 7, 10)) }),
  ]);
  assert.strictEqual(r.length, 2);
});

caso("Serviços e VCG deduplicam separadamente", () => {
  const r = Regras.implantacoes([
    linha({ matricula: "9", recurso: "RIOMLTIN-001" }),
    linha({ matricula: "9", recurso: "RIOVCGEXTIN-005" }),
  ]);
  assert.strictEqual(r.length, 2);
});

caso("só as três siglas são VCG; as demais são Serviços", () => {
  ["RIOVCGPOPIN-1", "RIOVCGEXTIN-1", "RIOVCGVENIN-1"].forEach((e) => {
    assert.strictEqual(linha({ recurso: e }).frente, "VCG", e);
  });
  ["RIOMLTIN-1", "RIORECIN-1", "RIOCOMIN-1"].forEach((e) => {
    assert.strictEqual(linha({ recurso: e }).frente, "SERVICOS", e);
  });
});

console.log("\nVENDA");
caso("Venda Potenciais/Factíveis de equipe comum é Comercial", () => {
  assert.strictEqual(Regras.canalDaVenda(
    linha({ atividade: "VENDA POTENCIAIS/FACTIVEIS", recurso: "RIORECIN-001" })), "COMERCIAL");
});

caso("113001 continua Comercial mesmo em RIOVCGVENIN", () => {
  assert.strictEqual(Regras.canalDaVenda(linha({
    atividade: "VENDA POTENCIAIS/FACTIVEIS", recurso: "RIOVCGVENIN-002", codigo: "113001-VENDA",
  })), "COMERCIAL");
});

caso("313001 entra em Venda VCG", () => {
  assert.strictEqual(Regras.canalDaVenda(linha({
    atividade: "LIGACAO DE AGUA", recurso: "RIOVCGEXTIN-005",
    codigo: "313001-VENDAS FACTIVEL AGUA",
  })), "VCG");
});

caso("114003 e 118048 vão para Outros Canais", () => {
  ["114003-X", "118048-Y"].forEach((codigo) => {
    assert.strictEqual(Regras.canalDaVenda(
      linha({ atividade: "VENDA POTENCIAIS/FACTIVEIS", codigo })), "OUTROS", codigo);
  });
});

caso("vendas deduplicam pelo ID da Atividade", () => {
  const r = Regras.vendas([
    linha({ id: "A1", atividade: "VENDA POTENCIAIS/FACTIVEIS", data: new Date(Date.UTC(2026, 7, 5)) }),
    linha({ id: "A1", atividade: "VENDA POTENCIAIS/FACTIVEIS", data: new Date(Date.UTC(2026, 7, 9)) }),
  ]);
  assert.strictEqual(r.length, 1);
});

console.log("\nTERMOS APLICADOS");
caso("finalizada com 110013 gera termo de Serviços", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "110013-TERMO", recurso: "RIOMLTIN-001" })), "SERVICOS");
});

caso("RIOVCGEXTIN + 310013 gera termo VCG", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "310013-TERMO", recurso: "RIOVCGEXTIN-005" })), "VCG");
});

caso("RIOVCGPOPIN + 310013 não entra no realizado VCG", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "310013-TERMO", recurso: "RIOVCGPOPIN-001" })), null);
});

caso("RIOVCGVENIN + 310013 não entra no realizado VCG", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "310013-TERMO", recurso: "RIOVCGVENIN-003" })), null);
});

caso("RIOVCGEXTIN com outro código de termo não gera termo", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "110013-TERMO", recurso: "RIOVCGEXTIN-005" })), null);
});

caso("o código também é procurado nas respostas de serviço", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "999999-OUTRO", extras: "310031-TERMO DE OCORRENCIA" })), "SERVICOS");
});

caso("Encerrada com Ocorrência também gera termo", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "210013-TERMO", status: "ENCERRADA COM OCORRENCIA" })), "SERVICOS");
});

caso("status fora da regra não gera termo", () => {
  assert.strictEqual(Regras.frenteDoTermo(
    linha({ codigo: "210013-TERMO", status: "CANCELADA" })), null);
});

caso("termos deduplicam pelo ID da Atividade", () => {
  const r = Regras.termos([
    linha({ id: "T1", codigo: "110013-TERMO", data: new Date(Date.UTC(2026, 7, 5)) }),
    linha({ id: "T1", codigo: "110013-TERMO", data: new Date(Date.UTC(2026, 7, 9)) }),
  ]);
  assert.strictEqual(r.length, 1);
});

console.log("\nSELEÇÃO DE ARQUIVOS");
caso("cópia (1) da mesma pasta é descartada, fica a maior", () => {
  const a = arquivo("Atividades-INTERIOR_21_08_26.xlsx", "Interior");
  const b = arquivo("Atividades-INTERIOR_21_08_26 (3).xlsx", "Interior");
  const escolhidos = Regras.selecionarCopias([a, b]);
  assert.strictEqual(escolhidos.size, 1);
  assert.ok(escolhidos.has(b));
});

caso("arquivos diferentes do mesmo dia NÃO são cópias", () => {
  const a = arquivo("Atividades-INTERIOR_21_08_26.xlsx", "Interior");
  const b = arquivo("Faturamento_21_08_26.xlsx", "Interior");
  assert.strictEqual(Regras.selecionarCopias([a, b]).size, 2);
});

caso("mesmo nome em subpastas diferentes NÃO é cópia", () => {
  const a = arquivo("Atividades.xlsx", "Interior");
  const b = arquivo("Atividades.xlsx", "Faturamento Termos");
  assert.strictEqual(Regras.selecionarCopias([a, b]).size, 2);
});

console.log("\nDATAS");
caso("aceita serial do Excel, dd/mm/aaaa e ISO", () => {
  assert.strictEqual(Regras.mesDe(Regras.data(46255)), "2026-08");
  assert.strictEqual(Regras.mesDe(Regras.data("21/08/2026")), "2026-08");
  assert.strictEqual(Regras.mesDe(Regras.data("2026-08-21")), "2026-08");
});

console.log("\nDIAS ÚTEIS");
caso("conta do dia 1 até o último dia com movimento", () => {
  // Agosto de 2026 começa num sábado; até o dia 10 há 6 dias úteis.
  const dias = Regras.diasUteis([linha({ data: new Date(Date.UTC(2026, 7, 10)) })]);
  assert.strictEqual(dias, 6);
});

console.log("\nARQUIVO ENTREGUE");
caso("regras.js não tem caractere fora do ASCII no código", () => {
  // Um acento dentro de uma regex ou de um texto do código quebra o painel
  // quando o navegador lê o arquivo em outra codificação: foi assim que a
  // faixa de acentos derrubou o dashboard inteiro.
  const fonte = fs.readFileSync(path.join(__dirname, "regras.js"), "utf8");
  let bloco = false;
  const sujas = [];
  fonte.split("\n").forEach((linhaFonte, i) => {
    let codigo = linhaFonte;
    if (bloco) {
      const fim = codigo.indexOf("*/");
      if (fim < 0) return;
      codigo = codigo.slice(fim + 2);
      bloco = false;
    }
    codigo = codigo.replace(/\/\*[\s\S]*?\*\//g, "");
    const abre = codigo.indexOf("/*");
    if (abre >= 0) { codigo = codigo.slice(0, abre); bloco = true; }
    codigo = codigo.replace(/\/\/.*$/, "");
    if ([...codigo].some((c) => c.codePointAt(0) > 126)) sujas.push(i + 1);
  });
  assert.deepStrictEqual(sujas, [], "linha(s) com acento no código: " + sujas);
});

caso("dashboard.html está em dia com regras.js e xlsx.full.min.js", () => {
  // O painel entregue é um arquivo só, com as bibliotecas embutidas. Se
  // alguém mexer em regras.js e esquecer de rodar gerar.js, o usuário abre
  // um dashboard com a regra antiga sem perceber.
  const entregue = fs.readFileSync(require("./gerar.js").SAIDA, "utf8");
  assert.strictEqual(entregue, require("./gerar.js").montar(),
    "rode: node offline/gerar.js");
});

console.log(`\n${passou} verificação(ões) passaram.`);
