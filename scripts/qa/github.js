// SPEC-06 pela interface e pelo webhook: ligar repositório, entregas assinadas do "GitHub" (simuladas), worker, fila de falhas.
// Uso: node github.js <saida> <usuario> <senha> <slug-do-projeto>  (segredo do webhook em VETOR_GITHUB_WEBHOOK_SECRET)
const crypto = require('crypto');
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw, slug] = process.argv.slice(2);
  const SEGREDO = process.env.VETOR_GITHUB_WEBHOOK_SECRET;
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
  const token = await p.evaluate(() => JSON.parse(localStorage.getItem('token')));
  const api = (m, url, d) => p.evaluate(async ([m, url, d, t]) => { const r = await fetch('/api/v1' + url, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: d ? JSON.stringify(d) : undefined }); return { s: r.status, j: await r.json().catch(() => null) }; }, [m, url, d, token]);
  const entregar = async (evento, payload, entrega, assinar = true) => {
    const corpo = JSON.stringify(payload);
    const h = { 'Content-Type': 'application/json', 'X-GitHub-Event': evento, 'X-GitHub-Delivery': entrega };
    if (assinar) h['X-Hub-Signature-256'] = 'sha256=' + crypto.createHmac('sha256', SEGREDO).update(corpo).digest('hex');
    const r = await fetch('http://localhost:9000/api/v1/vetor/github/webhook', { method: 'POST', headers: h, body: corpo });
    return `${r.status} ${JSON.stringify(await r.json())}`;
  };
  const esperar = async (cond) => { for (let i = 0; i < 40; i++) { const v = await cond(); if (v) return v; await p.waitForTimeout(500); } return null; };
  const proj = (await api('GET', `/projects/by_slug?slug=${slug}`)).j;
  const repoNome = `vetor-ficticio/portal-${Date.now() % 100000}`, rid = Date.now() % 1000000;
  // 1. Ligar repositório pela Administração
  await p.goto('http://localhost:9000/vetor/administracao/'); await p.waitForSelector('#novo-repo select option:nth-child(2)', { state: 'attached' });
  await p.selectOption('#novo-repo [name=projeto]', String(proj.id)); await p.fill('#novo-repo [name=nome]', repoNome); await p.click('#novo-repo button[type=submit]');
  await p.waitForSelector('#repo-msg.ok');
  console.log('1. ligar repositório →', await p.textContent('#repo-msg'), '| URL do webhook:', await p.textContent('#url-webhook'));
  await p.locator('h2', { hasText: 'Repositórios' }).scrollIntoViewIfNeeded();
  await p.screenshot({ path: `${out}/administracao-repositorios-1440.png` });
  // 2. Entregas: PR aberto citando a demanda, reenvio, sem assinatura
  const us = (await api('POST', '/userstories', { project: proj.id, subject: `[FICTÍCIO] Integrar login com SSO ${rid}` })).j;
  const repo = { id: rid, full_name: repoNome };
  const pr = (estado, merged, quando, numero = 12, pid = rid + 1) => ({ action: 'x', repository: repo, pull_request: { id: pid, number: numero, html_url: `https://github.com/${repoNome}/pull/${numero}`,
    title: `TG-${us.ref} Login com SSO`, body: '', state: estado, merged, draft: false, user: { login: 'dev-ficticio' }, updated_at: quando, head: { ref: `feature/tg-${us.ref}` } } });
  const id = `qa-${rid}`;
  console.log('2. PR aberto →', await entregar('pull_request', pr('open', false, '2026-10-23T10:00:00Z'), id + '-a'));
  const v1 = await esperar(async () => (await api('GET', `/vetor/vinculos-codigo?historia=${us.id}`)).j.find(v => v.estado === 'open'));
  console.log('   worker vinculou →', v1 ? `${v1.tipo} #${v1.numero} ${v1.estado}` : 'NADA');
  console.log('   reenvio da mesma entrega →', await entregar('pull_request', pr('open', false, '2026-10-23T10:00:00Z'), id + '-a'));
  console.log('   sem assinatura →', await entregar('pull_request', pr('open', false, '2026-10-23T10:00:00Z'), id + '-b', false));
  // 3. Segundo PR fechado sem merge e primeiro PR merged: etapa não muda sozinha
  const etapaAntes = (await api('GET', `/userstories/${us.id}`)).j.status;
  await entregar('pull_request', pr('closed', false, '2026-10-23T11:00:00Z', 13, rid + 2), id + '-c');
  await entregar('pull_request', pr('closed', true, '2026-10-23T12:00:00Z'), id + '-d');
  const lista = await esperar(async () => { const l = (await api('GET', `/vetor/vinculos-codigo?historia=${us.id}`)).j; return l.some(v => v.estado === 'merged') && l.length === 2 && l; });
  console.log('3. estados →', (lista || []).map(v => `#${v.numero} ${v.estado}`).join(', '), '| etapa mudou?', (await api('GET', `/userstories/${us.id}`)).j.status !== etapaAntes);
  console.log('   total de vínculos (sem duplicar) →', (lista || []).length);
  // 4. Demandas → Código
  await p.goto('http://localhost:9000/vetor/demandas/'); await p.waitForSelector('#f-projeto option:nth-child(2)', { state: 'attached' });
  await p.selectOption('#f-projeto', String(proj.id)); await p.waitForTimeout(1500);
  await p.locator('tbody tr', { hasText: `Integrar login com SSO ${rid}` }).locator('button', { hasText: 'Código' }).click();
  await p.waitForSelector('#codigo-conteudo li');
  console.log('4. tela Demandas → Código:', (await p.textContent('#codigo-conteudo')).replace(/\s+/g, ' ').trim());
  await p.screenshot({ path: `${out}/demandas-codigo-1440.png` });
  // 5. Falha de processamento (push com commit sem url) → fila de falhas → reprocessar pela tela
  console.log('5. push malformado →', await entregar('push', { repository: repo, commits: [{ id: 'f'.repeat(40), message: `TG-${us.ref} x` }] }, id + '-e'));
  const falha = await esperar(async () => (await api('GET', '/vetor/eventos-github?status=falhou')).j.find(e => e.entrega === id + '-e'));
  console.log('   fila →', falha ? `${falha.status}, tentativas ${falha.tentativas}, erro: ${falha.erro}` : 'NÃO ENTROU');
  await p.goto('http://localhost:9000/vetor/administracao/'); await p.waitForSelector('#falhas button');
  await p.locator('#falhas tr', { hasText: repoNome }).locator('button').first().click(); await p.waitForTimeout(1500);
  console.log('   reprocessar pela tela →', (await p.locator('#falhas tr', { hasText: repoNome }).locator('[role=status]').first().textContent()).trim());
  await p.locator('h2', { hasText: 'Repositórios' }).scrollIntoViewIfNeeded(); await p.mouse.wheel(0, 450); await p.waitForTimeout(300);
  await p.screenshot({ path: `${out}/fila-falhas-1440.png` });
  console.log('repositorio', repoNome);
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
