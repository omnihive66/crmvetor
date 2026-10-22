// Administração: link no menu só para administrador, painel, criação de conta e estados de acesso negado.
const { chromium } = require('playwright');
const login = async (b, user, pw, w = 1440) => {
  const p = await b.newPage({ viewport: { width: w, height: 900 } });
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]');
  await p.waitForURL(u => !u.pathname.startsWith('/login')); await p.waitForTimeout(4000); return p;
};
(async () => {
  const [out, admin, apw, obs, opw] = process.argv.slice(2); const b = await chromium.launch();
  for (const [user, pw] of [[admin, apw], [obs, opw]]) {
    const p = await login(b, user, pw);
    await p.click('.dropdown-user-navbar .chevron'); await p.waitForTimeout(500);
    console.log(`${user}: link Administração visível =`, await p.locator('.vetor-admin-link').isVisible());
    await p.goto('http://localhost:9000/vetor/administracao/'); await p.waitForTimeout(2500);
    console.log(`${user}: página mostra →`, (await p.textContent('main')).replace(/\s+/g, ' ').trim().slice(0, 90));
    await p.screenshot({ path: `${out}/administracao-${user}-1440.png`, fullPage: true }); await p.close();
  }
  const p = await login(b, admin, apw, 390); await p.goto('http://localhost:9000/vetor/administracao/'); await p.waitForTimeout(2500);
  await p.screenshot({ path: `${out}/administracao-390.png`, fullPage: true });
  console.log('390px: rolagem horizontal da página =', await p.evaluate(() => document.documentElement.scrollWidth - innerWidth), 'px');
  // Ações pela interface (dados fictícios).
  const a = await login(b, admin, apw); await a.goto('http://localhost:9000/vetor/administracao/'); await a.waitForSelector('#nova');
  await a.fill('#nova [name=full_name]', '[FICTÍCIO] Dev Teste'); await a.fill('#nova [name=username]', 'dev.teste');
  await a.fill('#nova [name=email]', 'dev.teste@vetor.local'); await a.selectOption('#nova [name=papel]', 'desenvolvedor');
  await a.click('#nova button[type=submit]'); await a.waitForTimeout(2000);
  console.log('criar conta →', await a.textContent('#nova-msg'));
  await a.click('#nova button[type=submit]'); await a.waitForTimeout(1500);
  console.log('criar de novo →', await a.textContent('#nova-msg'));
  const linha = n => a.locator('#pessoas tr', { hasText: n });
  await linha('admin.dev').locator('select').selectOption('gestor'); await linha('admin.dev').locator('button').click(); await a.waitForTimeout(1500);
  console.log('rebaixar único administrador →', await linha('admin.dev').locator('[role=status]').textContent(),
              '| select voltou para', await linha('admin.dev').locator('select').inputValue());
  await linha('observador.dev').locator('input[type=checkbox]').first().check(); await linha('observador.dev').locator('button').click(); await a.waitForTimeout(1500);
  console.log('dar ver custos ao observador →', await linha('observador.dev').locator('[role=status]').textContent());
  await a.screenshot({ path: `${out}/administracao-acoes-1440.png`, fullPage: true });
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
