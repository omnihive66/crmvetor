// QA visual do CRM: clientes (cartões/tabela), cliente (abas), busca, shell no app do Taiga e gaveta no celular.
const { chromium } = require('playwright');
const entrar = async (ctx, user, pw) => {
  const p = await ctx.newPage(); await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]');
  await p.waitForURL(u => !u.pathname.startsWith('/login')); await p.waitForTimeout(2500); return p;
};
(async () => {
  const [out, user, pw, cliente, slug, obs, opw] = process.argv.slice(2); const b = await chromium.launch();
  const erros = [];
  for (const [w, h] of [[1440, 900], [1024, 768], [390, 844]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } }); const p = await entrar(ctx, user, pw);
    p.on('pageerror', e => erros.push(`${w}: ${e.message}`));
    const foto = async (n, full = false) =>  // página inteira distorce elementos fixos (barra lateral)
      { await p.waitForTimeout(1200); await p.screenshot({ path: `${out}/${n}-${w}.png`, fullPage: full }); };
    const rolagem = () => p.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    await p.goto('http://localhost:9000/vetor/clientes/'); await p.waitForSelector('.grade, .tabela, .estado'); await foto('clientes-cartoes');
    await p.click('#ver-tabela'); await p.waitForSelector('table'); await foto('clientes-tabela');
    const rolTab = await rolagem();
    await p.click('#ver-cartoes');
    for (const aba of ['resumo', 'documentos', 'reunioes']) {
      await p.goto(`http://localhost:9000/vetor/clientes/cliente.html?id=${cliente}&aba=${aba}`); await p.waitForSelector('[role=tabpanel] h2'); await foto(`cliente-${aba}`);
    }
    const rolCli = await rolagem();
    await p.goto('http://localhost:9000/vetor/busca/?q=FICT'); await p.waitForSelector('#resultado section, #resultado .estado'); await foto('busca');
    await p.goto(`http://localhost:9000/project/${slug}/kanban`); await p.waitForTimeout(3000); await foto('quadro-com-shell', false);
    if (w === 390) {
      await p.goto('http://localhost:9000/vetor/clientes/'); await p.waitForSelector('.vt-shell-abrir');
      await p.click('.vt-shell-abrir'); await foto('gaveta-aberta', false);
      console.log('390: foco ao abrir a gaveta =', await p.evaluate(() => document.activeElement.getAttribute('aria-label')));
      await p.keyboard.press('Escape'); await p.waitForTimeout(300);
      console.log('390: Esc fecha a gaveta =', !(await p.evaluate(() => document.documentElement.classList.contains('vt-shell-aberto'))));
    }
    console.log(`${w}: rolagem horizontal clientes(tabela)=${rolTab}px cliente=${rolCli}px | título: ${await p.title()}`);
    await ctx.close();
  }
  // Somente leitura: observador.
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } }); const p = await entrar(ctx, obs, opw);
  await p.goto(`http://localhost:9000/vetor/clientes/cliente.html?id=${cliente}&aba=documentos`); await p.waitForSelector('[role=tabpanel] h2'); await p.waitForTimeout(800);
  console.log('observador: botões de edição =', await p.locator('button:has-text("Arquivar"), button:has-text("Remover"), button:has-text("Adicionar")').count(),
              '| Novo cliente visível =', await p.goto('http://localhost:9000/vetor/clientes/').then(() => p.waitForTimeout(1500)).then(() => p.locator('#novo').isVisible()));
  await p.screenshot({ path: `${out}/clientes-observador-1440.png` });
  console.log('erros de JavaScript:', erros.length ? erros : 'nenhum');
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
