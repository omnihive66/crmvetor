// Menu do projeto visto por um usuário só leitura: itens de administração não devem aparecer.
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw, slug] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]');
  await p.waitForURL(u => !u.pathname.startsWith('/login'));
  await p.goto(`http://localhost:9000/project/${slug}/kanban`); await p.waitForTimeout(3000);
  const menu = await p.$$eval('tg-project-menu a, tg-project-menu button', els => els.map(e => e.textContent.trim()).filter(Boolean));
  console.log(`${user} vê no menu do projeto:`, menu.join(' | '));
  await p.screenshot({ path: `${out}/quadro-observador-1440.png` }); await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
