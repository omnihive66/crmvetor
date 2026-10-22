// Estados de erro com a marca: rota inexistente e projeto sem permissão.
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1024, height: 768 } });
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]');
  await p.waitForURL(u => !u.pathname.startsWith('/login'));
  for (const [n, path] of [['nao-encontrado', '/project/nao-existe/kanban'], ['sem-permissao', '/project/ficticio-teste-de-backup/kanban']]) {
    await p.goto('http://localhost:9000' + path); await p.waitForTimeout(3000);
    console.log(n, '|', (await p.textContent('body')).replace(/\s+/g, ' ').trim().slice(0, 120));
    await p.screenshot({ path: `${out}/${n}-1024.png` });
  }
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
