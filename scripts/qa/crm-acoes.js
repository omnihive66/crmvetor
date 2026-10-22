// Ações do CRM pela interface (dados fictícios): cadastro com nome repetido, envio de arquivo,
// demanda a partir de reunião, filtros persistidos no servidor e busca pela barra lateral.
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw, cliente, arquivo] = process.argv.slice(2);
  const b = await chromium.launch(); const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } }); const p = await ctx.newPage();
  p.on('dialog', d => d.accept());
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
  // 1. Nome repetido pede confirmação
  await p.goto('http://localhost:9000/vetor/clientes/'); await p.waitForSelector('#novo:not([hidden])'); await p.click('#novo');
  await p.fill('#form-novo [name=nome]', '[FICTÍCIO] Beta Logística'); await p.click('#novo-salvar'); await p.waitForTimeout(1200);
  console.log('1. nome repetido →', await p.textContent('#novo-msg'), '| botão:', await p.textContent('#novo-salvar'));
  await p.click('#novo-cancelar');
  // 2. Filtro persistido no servidor (userstorage): recarrega em outro contexto e o filtro continua
  await p.selectOption('#f-ciclo', 'operacao'); await p.click('#ver-tabela'); await p.waitForTimeout(1500);
  const novo = await ctx.newPage(); await novo.goto('http://localhost:9000/vetor/clientes/'); await novo.waitForSelector('table'); await novo.waitForTimeout(800);
  console.log('2. depois de recarregar: ciclo =', await novo.inputValue('#f-ciclo'), '| modo tabela =', await novo.getAttribute('#ver-tabela', 'aria-pressed'),
              '| linhas =', await novo.locator('tbody tr').count());
  await novo.selectOption('#f-ciclo', ''); await novo.click('#ver-cartoes'); await novo.waitForTimeout(1200); await novo.close();
  // 3. Envio de arquivo pela tela (título único por execução)
  const titulo = `[FICTÍCIO] Contrato ${Date.now()}`;
  await p.goto(`http://localhost:9000/vetor/clientes/cliente.html?id=${cliente}&aba=documentos`); await p.waitForSelector('form');
  await p.fill('form [name=titulo]', titulo); await p.selectOption('form [name=categoria]', 'contrato');
  await p.setInputFiles('form [name=arquivo]', arquivo); await p.click('form button[type=submit]'); await p.waitForTimeout(1500);
  console.log('3. documento enviado →', await p.locator('li', { hasText: titulo }).count() === 1);
  const [download] = await Promise.all([p.waitForEvent('download', { timeout: 10000 }).catch(() => null),
    p.locator('li', { hasText: titulo }).locator('button', { hasText: 'Baixar' }).click()]);
  console.log('   download pela tela →', download ? download.suggestedFilename() : 'navegou para o arquivo (sem evento de download)');
  // 4. Demanda a partir da reunião
  await p.goto(`http://localhost:9000/vetor/clientes/cliente.html?id=${cliente}&aba=reunioes`); await p.waitForSelector('li form');
  await p.locator('li form button[type=submit]').first().click(); await p.waitForTimeout(1500);
  const link = p.locator('li a[href*="/us/"]').first();
  console.log('4. demanda criada →', await link.textContent(), await link.getAttribute('href'));
  await link.click(); await p.waitForURL(/\/us\//); await p.waitForTimeout(2500);
  console.log('   abre no Taiga →', await p.title());
  await p.screenshot({ path: `${out}/demanda-da-reuniao-1440.png` });
  // 5. Busca pela barra lateral
  await p.goto('http://localhost:9000/vetor/clientes/'); await p.waitForSelector('.vt-shell input');
  await p.fill('.vt-shell input', 'cronograma'); await p.press('.vt-shell input', 'Enter'); await p.waitForFunction(() => !/Buscando/.test(document.getElementById('resultado')?.textContent || 'Buscando'));
  console.log('5. busca "cronograma" →', (await p.textContent('#resultado')).replace(/\s+/g, ' ').trim().slice(0, 120));
  await p.screenshot({ path: `${out}/busca-cronograma-1440.png` });
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
