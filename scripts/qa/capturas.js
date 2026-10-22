// Capturas de QA visual: login, início, quadro e card em 1440/1024/390 px.
const { chromium } = require('playwright');
(async () => {
  const [out, pw, slug] = process.argv.slice(2);
  const b = await chromium.launch();
  for (const [w, h] of [[1440, 900], [1024, 768], [390, 844]]) {
    const ctx = await b.newContext({ viewport: { width: w, height: h } }); const p = await ctx.newPage();
    const shot = async (n) => { await p.waitForTimeout(1500); await p.screenshot({ path: `${out}/${n}-${w}.png` }); };
    await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]'); await shot('login');
    await p.fill('input[name=username]', 'admin.dev'); await p.fill('input[name=password]', pw);
    await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
    await shot('inicio');
    await p.goto(`http://localhost:9000/project/${slug}/kanban`); await p.waitForSelector('.kanban-table, tg-kanban', { timeout: 20000 }); await shot('quadro');
    await p.goto(`http://localhost:9000/project/${slug}/us/2`); await p.waitForSelector('.detail-title-text, .us-detail', { timeout: 20000 }); await shot('card');
    console.log(w, 'ok |', await p.title()); await ctx.close();
  }
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
