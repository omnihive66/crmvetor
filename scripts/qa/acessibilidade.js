// SPEC-10: auditoria automática de acessibilidade (axe-core, WCAG 2.1 A/AA) das telas próprias da Vetor, em desktop e celular.
// Uso: AXE=<caminho do axe.min.js> node acessibilidade.js <usuario> <senha> <id-de-um-cliente>
const fs = require('fs');
const { chromium } = require('playwright');
(async () => {
  const [user, pw, cliente] = process.argv.slice(2);
  const axe = fs.readFileSync(process.env.AXE, 'utf8');
  const telas = ['vetor/clientes/', `vetor/clientes/cliente.html?id=${cliente}`, `vetor/clientes/cliente.html?id=${cliente}&aba=operacao`,
    `vetor/clientes/cliente.html?id=${cliente}&aba=custos`, 'vetor/demandas/', 'vetor/minhas-demandas/', 'vetor/monitoramento/',
    'vetor/custos/', 'vetor/busca/?q=Carga', 'vetor/administracao/'];
  const b = await chromium.launch();
  let total = 0;
  for (const [rotulo, viewport] of [['1440', { width: 1440, height: 900 }], ['390', { width: 390, height: 844 }]]) {
    const p = await (await b.newContext({ viewport })).newPage();
    await p.goto('http://localhost:9000/login'); await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw);
    await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
    for (const t of telas) {
      await p.goto(`http://localhost:9000/${t}`); await p.waitForTimeout(2500);
      await p.addScriptTag({ content: axe });
      const r = await p.evaluate(async () => (await axe.run(document, { runOnly: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'] })).violations
        .map(v => ({ id: v.id, impacto: v.impact, alvos: v.nodes.slice(0, 3).map(n => n.target.join(' ')), n: v.nodes.length })));
      total += r.length;
      console.log(`${rotulo} ${t} → ${r.length ? r.map(v => `${v.impacto} ${v.id} (${v.n}): ${v.alvos.join(' | ')}`).join(' ; ') : 'sem violações'}`);
    }
  }
  console.log(`total de regras violadas: ${total}`);
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
