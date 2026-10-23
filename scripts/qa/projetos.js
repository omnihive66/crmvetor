// SPEC-04 pela interface: projeto pelo modelo Kanban (fluxo Vetor), mover por teclado, conflito e participação.
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
  const token = await p.evaluate(() => JSON.parse(localStorage.getItem('token')));
  const api = (m, url, d) => p.evaluate(async ([m, url, d, t]) => { const r = await fetch('/api/v1' + url, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: d ? JSON.stringify(d) : undefined }); return { s: r.status, j: await r.json().catch(() => null) }; }, [m, url, d, token]);
  // 1. Criar projeto pela tela, opção Kanban
  await p.goto('http://localhost:9000/project/new'); await p.waitForTimeout(1500);
  console.log('1. opção Kanban na tela →', (await p.textContent('a[tg-nav="create-project-kanban"]')).replace(/\s+/g, ' ').trim());
  await p.click('a[tg-nav="create-project-kanban"]'); await p.waitForSelector('input[name=project-name], #project-name, input[ng-model*="name"]');
  const nome = `[FICTÍCIO] Implantação ${Date.now() % 100000}`;
  await p.fill('input[ng-model="vm.projectForm.name"]', nome); await p.fill('textarea[ng-model="vm.projectForm.description"]', 'Projeto fictício de validação do fluxo');
  await p.click('button[type=submit]'); await p.waitForURL(/\/project\/[^/]+\/kanban/, { timeout: 30000 }); await p.waitForTimeout(3000);
  const colunas = await p.$$eval('.task-colum-name > span, .kanban-table-header .title', els => els.map(e => e.textContent.trim()).filter(Boolean));
  console.log('   colunas criadas →', colunas.join(' | '));
  await p.screenshot({ path: `${out}/quadro-fluxo-vetor-1440.png` });
  const slug = new URL(p.url()).pathname.split('/')[2];
  const proj = (await api('GET', `/projects/by_slug?slug=${slug}`)).j;
  const st = Object.fromEntries((await api('GET', `/userstory-statuses?project=${proj.id}`)).j.map(s => [s.name, s.id]));
  const me = (await api('GET', '/users/me')).j;
  const us = (await api('POST', '/userstories', { project: proj.id, subject: '[FICTÍCIO] Configurar acesso', status: st['A fazer'], assigned_to: me.id, due_date: new Date(Date.now() + 2 * 864e5).toISOString().slice(0, 10) })).j;
  // 2. Mover por teclado na tela Demandas
  await p.goto(`http://localhost:9000/vetor/demandas/`); await p.waitForSelector('table');
  await p.selectOption('#f-projeto', String(proj.id)); await p.waitForTimeout(1200); await p.waitForSelector('tbody tr select');
  const sel = p.locator('tbody tr select').first();
  await sel.focus(); await p.keyboard.press('ArrowDown'); await p.waitForTimeout(1500);  // Chromium: seta no select fechado troca a opção e dispara change
  console.log('2. teclado (seta para baixo) →', await p.locator('tbody tr [role=status]').first().textContent());
  const depois = (await api('GET', `/userstories/${us.id}`)).j;
  console.log('   etapa gravada →', Object.entries(st).find(([, id]) => id === depois.status)[0]);
  // 3. Conflito: outra pessoa muda a etapa por fora; a tela ainda tem a versão antiga
  await api('PATCH', `/userstories/${us.id}`, { status: st['Revisão'], version: depois.version });
  await sel.focus(); await p.keyboard.press('ArrowDown'); await p.waitForTimeout(1500);
  const msg = await p.locator('tbody tr [role=status]').first().textContent();
  const final = (await api('GET', `/userstories/${us.id}`)).j;
  console.log('3. conflito →', msg, '| select:', await sel.evaluate(s => s.selectedOptions[0].text), '| coluna Etapa:', await p.locator('tbody tr .etapa').first().textContent(), '| banco:', Object.entries(st).find(([, id]) => id === final.status)[0]);
  await p.screenshot({ path: `${out}/demandas-conflito-1440.png` });
  // 4. Participação por etapa
  await p.reload(); await p.waitForSelector('tbody tr button'); await p.selectOption('#f-projeto', String(proj.id)); await p.waitForTimeout(1200);
  await p.locator('tbody tr button', { hasText: 'Etapas' }).first().click(); await p.waitForSelector('#dlg-etapas table, #dlg-etapas p');  await p.waitForTimeout(600);
  console.log('4. participação →', (await p.textContent('#etapas-conteudo')).replace(/\s+/g, ' ').trim().slice(0, 220));
  await p.screenshot({ path: `${out}/participacao-1440.png` });
  console.log('projeto', slug);
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
