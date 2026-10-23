// SPEC-10: fluxo ponta a ponta cliente → projeto → tarefa → colaboração → código → incidente → resolução (dados [FICTÍCIO]).
// Uso: node fim-a-fim.js <saida> <usuario> <senha>  (VETOR_GITHUB_WEBHOOK_SECRET e VETOR_KUMA_TOKEN no ambiente)
const crypto = require('crypto');
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto('http://localhost:9000/login'); await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw);
  await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
  const token = await p.evaluate(() => JSON.parse(localStorage.getItem('token')));
  const api = (m, url, d) => p.evaluate(async ([m, url, d, t]) => { const r = await fetch('/api/v1' + url, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: d ? JSON.stringify(d) : undefined }); return { s: r.status, j: await r.json().catch(() => null) }; }, [m, url, d, token]);
  const post = async (url, corpo, h) => { const r = await fetch('http://localhost:9000/api/v1' + url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...h }, body: corpo }); return r.status; };
  const esperar = async f => { for (let i = 0; i < 40; i++) { const v = await f(); if (v) return v; await p.waitForTimeout(500); } return null; };
  const passo = (n, t, ok) => console.log(`${ok ? 'OK ' : 'ERRO'} ${n}. ${t}`);
  const n = Date.now() % 100000;
  // 1. Cliente
  const cli = (await api('POST', '/vetor/clientes', { nome: `[FICTÍCIO] Fim a Fim ${n}`, ciclo: 'implantacao' })).j;
  passo(1, `cliente "${cli.nome}"`, !!cli.id);
  // 2. Projeto (modelo Kanban fluxo Vetor) ligado ao cliente
  const proj = (await api('POST', '/projects', { name: `[FICTÍCIO] Implantação ${n}`, description: 'fluxo ponta a ponta', creation_template: 1001 })).j;
  const vinc = await api('POST', `/vetor/clientes/${cli.id}/vincular_projeto`, { projeto: proj.id });
  passo(2, `projeto "${proj.name}" ligado ao cliente`, vinc.s === 200);
  // 3. Tarefa (demanda) com responsável
  const st = Object.fromEntries((await api('GET', `/userstory-statuses?project=${proj.id}`)).j.map(s => [s.name, s.id]));
  const me = (await api('GET', '/users/me')).j;
  let us = (await api('POST', '/userstories', { project: proj.id, subject: '[FICTÍCIO] Publicar portal do cliente', assigned_to: me.id, status: st['A fazer'] })).j;
  passo(3, `demanda #${us.ref} em "A fazer"`, !!us.id);
  // 4. Colaboração: pergunta, resposta e avanço de etapa (histórico separado da conversa)
  for (const c of ['Qual domínio usamos?', 'portal.ficticio.example, já com TLS.']) us = (await api('PATCH', `/userstories/${us.id}`, { comment: c, version: us.version })).j;
  us = (await api('PATCH', `/userstories/${us.id}`, { status: st['Desenvolvimento'], version: us.version })).j;
  const hist = (await api('GET', `/history/userstory/${us.id}`)).j;
  passo(4, `colaboração: ${hist.filter(h => h.comment).length} comentários e mudança de etapa no histórico`, hist.filter(h => h.comment).length === 2);
  // 5. Código: repositório ligado e PR assinado citando a demanda
  const repo = `vetor-ficticio/fim-a-fim-${n}`;
  await api('POST', '/vetor/repositorios', { projeto: proj.id, nome: repo });
  const pr = estado => JSON.stringify({ action: 'x', repository: { id: 7000000 + n, full_name: repo }, pull_request: { id: 8000000 + n, number: 1, html_url: `https://github.com/${repo}/pull/1`,
    title: `TG-${us.ref} Publica portal`, body: '', state: estado === 'merged' ? 'closed' : 'open', merged: estado === 'merged', draft: false, user: { login: 'dev-ficticio' },
    updated_at: estado === 'merged' ? '2026-10-23T12:00:00Z' : '2026-10-23T10:00:00Z', head: { ref: 'feature/portal' } } });
  const enviarPr = async (estado, entrega) => { const c = pr(estado); return post('/vetor/github/webhook', c, { 'X-GitHub-Event': 'pull_request', 'X-GitHub-Delivery': entrega,
    'X-Hub-Signature-256': 'sha256=' + crypto.createHmac('sha256', process.env.VETOR_GITHUB_WEBHOOK_SECRET).update(c).digest('hex') }); };
  await enviarPr('open', `e2e-${n}-a`);
  const v = await esperar(async () => (await api('GET', `/vetor/vinculos-codigo?historia=${us.id}`)).j[0]);
  passo(5, `PR #1 ligado à demanda (${v && v.estado})`, v && v.estado === 'open');
  // 6. Incidente: queda do monitor do portal → triagem → mapeado ao projeto → demanda de incidente
  const mid = 9000000 + n, kuma = (status, hm) => JSON.stringify({ heartbeat: { monitorID: mid, status, time: `2026-10-23 ${hm}:00.000`, msg: status ? '200 - OK' : 'timeout', important: true },
    monitor: { id: mid, name: `[FICTÍCIO] Portal ${n}`, type: 'http', url: 'https://portal.ficticio.example/' }, msg: 'x' });
  await post('/vetor/monitoramento/kuma/webhook', kuma(0, '11:00'), { 'X-Vetor-Token': process.env.VETOR_KUMA_TOKEN });
  const rec = await esperar(async () => (await api('GET', '/vetor/recursos-monitorados?triagem=true')).j.find(r => r.id_externo === String(mid)));
  await api('PATCH', `/vetor/recursos-monitorados/${rec.id}`, { projeto: proj.id });
  const inc = await esperar(async () => (await api('GET', '/vetor/incidentes?estado=aberto')).j.find(i => i.recurso.id === rec.id && i.demanda));
  passo(6, `incidente aberto com demanda #${inc && inc.demanda.ref} no projeto`, !!inc);
  // 7. Resolução: monitor volta, PR merged, demanda concluída por uma pessoa (nada conclui sozinho)
  await post('/vetor/monitoramento/kuma/webhook', kuma(1, '11:20'), { 'X-Vetor-Token': process.env.VETOR_KUMA_TOKEN });
  await enviarPr('merged', `e2e-${n}-b`);
  const rec2 = await esperar(async () => (await api('GET', `/vetor/incidentes/${inc.id}`)).j.estado === 'recuperado');
  const v2 = await esperar(async () => ((await api('GET', `/vetor/vinculos-codigo?historia=${us.id}`)).j[0] || {}).estado === 'merged');
  const antes = (await api('GET', `/userstories/${us.id}`)).j;
  passo(7, `monitor recuperado (${!!rec2}), PR merged (${!!v2}), demanda ainda em "${Object.keys(st).find(k => st[k] === antes.status)}" até alguém concluir`, rec2 && v2 && antes.status === st['Desenvolvimento']);
  const fim = (await api('PATCH', `/userstories/${us.id}`, { status: st['Concluído'], version: antes.version })).j;
  const incUs = (await api('GET', `/userstories/by_ref?ref=${inc.demanda.ref}&project=${proj.id}`)).j;
  await api('PATCH', `/userstories/${incUs.id}`, { status: st['Concluído'], version: incUs.version });
  passo(8, `demanda concluída por ${me.username}: ${fim.is_closed}`, fim.is_closed);
  // 9. Visão do cliente
  const painel = (await api('GET', `/vetor/clientes/${cli.id}/painel`)).j;
  passo(9, `painel do cliente: ${painel.disponibilidade.length} monitor (quedas em 30 dias: ${painel.disponibilidade[0].quedas_30d}), pendências abertas: ${painel.relacionamento.pendencias.abertas}`,
    painel.disponibilidade[0].quedas_30d === 1 && painel.relacionamento.pendencias.abertas === 0);
  await p.goto(`http://localhost:9000/vetor/clientes/cliente.html?id=${cli.id}&aba=operacao`); await p.waitForSelector('section[aria-label="Disponibilidade do produto"] li');
  await p.screenshot({ path: `${out}/fim-a-fim-cliente-1440.png` });
  await p.goto(`http://localhost:9000/project/${proj.slug}/us/${us.ref}`); await p.waitForTimeout(3500);
  await p.screenshot({ path: `${out}/fim-a-fim-demanda-1440.png` });
  await b.close();
})().catch(e => { console.error('ERRO', e.message); process.exit(1); });
