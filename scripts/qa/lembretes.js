// SPEC-05 pela interface: lembrete privado, aviso pelo worker, conversão com prévia, token do agente e privacidade.
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw, outro, outroPw, projetoSlug] = process.argv.slice(2);
  const b = await chromium.launch();
  const entrar = async (u, s, viewport = { width: 1440, height: 900 }) => {
    const p = await (await b.newContext({ viewport })).newPage();
    await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
    await p.fill('input[name=username]', u); await p.fill('input[name=password]', s); await p.click('button[type=submit]'); await p.waitForURL(x => !x.pathname.startsWith('/login'));
    const token = await p.evaluate(() => JSON.parse(localStorage.getItem('token')));
    p.api = (m, url, d, h = {}) => p.evaluate(async ([m, url, d, t, h]) => { const r = await fetch('/api/v1' + url, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t, ...h }, body: d ? JSON.stringify(d) : undefined }); return { s: r.status, j: await r.json().catch(() => null) }; }, [m, url, d, token, h]);
    return p;
  };
  const p = await entrar(user, pw);
  // 1. Criar lembrete pela tela, já vencido (1 minuto atrás, horário de Brasília)
  await p.goto('http://localhost:9000/vetor/minhas-demandas/'); await p.waitForSelector('#lembretes .card');
  await p.click('#novo'); await p.fill('#form-lembrete [name=titulo]', '[FICTÍCIO] Ligar para o cliente sobre a proposta');
  await p.fill('#form-lembrete [name=notas]', 'Nota privada: margem mínima 12%');
  const local = new Intl.DateTimeFormat('sv-SE', { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' }).format(new Date(Date.now() - 60000)).replace(' ', 'T');
  await p.fill('#form-lembrete [name=vencimento]', local); await p.click('#form-lembrete button[type=submit]');
  await p.waitForSelector('#lembretes tbody tr');
  console.log('1. lembrete criado pela tela →', (await p.textContent('#lembretes tbody tr td:nth-child(2)')).trim(), '(campo local', local + ')');
  const lid = (await p.api('GET', '/vetor/lembretes')).j.find(l => l.titulo.includes('Ligar para o cliente')).id;
  // 2. O worker (beat a cada 60 s) avisa; a barra lateral mostra o número
  let resumo;
  for (let i = 0; i < 30; i++) { resumo = (await p.api('GET', '/vetor/lembretes/resumo')).j; if (resumo.avisos_nao_vistos) break; await p.waitForTimeout(5000); }
  await p.goto('http://localhost:9000/vetor/demandas/'); await p.waitForSelector('.vt-shell-aviso');
  console.log('2. aviso do worker →', resumo, '| barra lateral:', (await p.textContent('.vt-shell-aviso')).trim());
  await p.screenshot({ path: `${out}/aviso-barra-1440.png` });
  await p.goto('http://localhost:9000/vetor/minhas-demandas/'); await p.waitForSelector('#lembretes tbody tr'); await p.waitForTimeout(1500);
  console.log('   depois de abrir a lista → aviso na barra:', await p.$('.vt-shell-aviso') ? 'ainda aparece' : 'sumiu', '| api:', (await p.api('GET', '/vetor/lembretes/resumo')).j);
  await p.screenshot({ path: `${out}/minhas-demandas-1440.png` });
  // 3. Privacidade: outra pessoa (observador) não vê pela lista nem pelo ID nem pela busca
  const q = await entrar(outro, outroPw);
  console.log('3. outra pessoa → lista:', (await q.api('GET', '/vetor/lembretes')).j.length, '| por ID:', (await q.api('GET', `/vetor/lembretes/${lid}`)).s,
    '| busca:', JSON.stringify((await q.api('GET', '/vetor/busca?q=Ligar%20para%20o%20cliente')).j).includes('Ligar para o cliente') ? 'ACHOU' : 'nada');
  // 4. Conversão com prévia e confirmação; repetir não duplica
  const proj = (await p.api('GET', `/projects/by_slug?slug=${projetoSlug}`)).j;
  await p.locator('#lembretes tbody tr', { hasText: 'Ligar para o cliente' }).locator('button', { hasText: 'Virar demanda' }).click();
  await p.selectOption('#c-projeto', String(proj.id)); await p.waitForSelector('#c-previa dl');
  console.log('4. prévia →', (await p.textContent('#c-previa')).replace(/\s+/g, ' ').trim());
  await p.screenshot({ path: `${out}/conversao-previa-1440.png` });
  await p.click('#c-confirmar'); await p.waitForSelector('#c-previa .ok');
  console.log('   confirmado →', (await p.textContent('#c-previa .ok')).trim());
  const repetida = await p.api('POST', `/vetor/lembretes/${lid}/converter`, { projeto: proj.id, confirmar: true });
  const iguais = (await p.api('GET', `/userstories?project=${proj.id}`)).j.filter(u => u.subject.includes('Ligar para o cliente')).length;
  console.log('   repetição →', repetida.s, repetida.j.criada === false ? 'mesma demanda' : 'NOVA', '| demandas com esse assunto:', iguais);
  await p.keyboard.press('Escape');
  // 5. Token do agente pela tela, uso pela rota do agente, ambiguidade, revogação
  await p.click('#novo-token'); await p.fill('#form-token [name=nome]', '[FICTÍCIO] Assistente de teste'); await p.click('#token-criar');
  await p.waitForSelector('#token-resultado .token');
  const token = (await p.textContent('#token-resultado .token')).trim();
  await p.screenshot({ path: `${out}/token-criado-1440.png` });
  await p.keyboard.press('Escape');
  const ag = (d, chave) => p.evaluate(async ([d, t, chave]) => { const r = await fetch('/api/v1/vetor/agente/lembretes', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Agente ' + t, 'Idempotency-Key': chave }, body: JSON.stringify(d) }); return { s: r.status, j: await r.json().catch(() => null) }; }, [d, token, chave]);
  const chave = 'qa-' + Date.now(), a1 = await ag({ titulo: '[FICTÍCIO] Pelo agente' }, chave), a2 = await ag({ titulo: '[FICTÍCIO] Pelo agente' }, chave);
  console.log('5. agente cria →', a1.s, JSON.stringify(a1.j), '| mesma chave de novo:', a2.s, a2.j.id === a1.j.id ? 'mesmo lembrete' : 'OUTRO');
  console.log('   projeto inexistente →', JSON.stringify((await ag({ titulo: 'x', projeto: 'Projeto que não existe' }, 'qa-amb-' + Date.now())).j));
  console.log('   token em outra rota →', await p.evaluate(async t => (await fetch('/api/v1/users/me', { headers: { Authorization: 'Agente ' + t } })).status, token));
  await p.reload(); await p.waitForSelector('#tokens li');
  p.once('dialog', d => d.accept()); await p.locator('#tokens li', { hasText: 'Assistente de teste' }).locator('button', { hasText: 'Revogar' }).first().click(); await p.waitForTimeout(1200);
  console.log('   depois de revogar →', (await ag({ titulo: 'x' }, 'qa-rev-' + Date.now())).s);
  // 6. Celular
  const m = await entrar(user, pw, { width: 390, height: 844 });
  await m.goto('http://localhost:9000/vetor/minhas-demandas/'); await m.waitForSelector('#lembretes .card'); await m.waitForTimeout(800);
  console.log('6. celular → rolagem horizontal da página:', await m.evaluate(() => document.documentElement.scrollWidth > innerWidth));
  await m.screenshot({ path: `${out}/minhas-demandas-390.png` });
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
