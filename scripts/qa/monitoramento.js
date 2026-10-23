// SPEC-07 pela interface e pelos webhooks: Kuma e Beszel (formatos das versões 2.5.7 e v0.21.1) → triagem → incidente com linha do tempo.
// Uso: node monitoramento.js <saida> <usuario> <senha> <slug>  (tokens em VETOR_KUMA_TOKEN e VETOR_BESZEL_TOKEN)
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw, slug] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
  const token = await p.evaluate(() => JSON.parse(localStorage.getItem('token')));
  const api = (m, url, d) => p.evaluate(async ([m, url, d, t]) => { const r = await fetch('/api/v1' + url, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: d ? JSON.stringify(d) : undefined }); return { s: r.status, j: await r.json().catch(() => null) }; }, [m, url, d, token]);
  const enviar = async (prov, dados, tok = process.env[`VETOR_${prov.toUpperCase()}_TOKEN`]) => {
    const r = await fetch(`http://localhost:9000/api/v1/vetor/monitoramento/${prov}/webhook`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(tok ? { 'X-Vetor-Token': tok } : {}) }, body: JSON.stringify(dados) });
    return r.status;
  };
  const esperar = async (cond) => { for (let i = 0; i < 40; i++) { const v = await cond(); if (v) return v; await p.waitForTimeout(500); } return null; };
  const mid = Date.now() % 1000000, nome = `[FICTÍCIO] API Portal ${mid}`, dia = new Date().toISOString().slice(0, 10);
  const kuma = (status, hm) => ({ heartbeat: { monitorID: mid, status, time: `${dia} ${hm}:00.000`, msg: status === 0 ? 'connect ECONNREFUSED' : '200 - OK', ping: 80, important: true, duration: 60 },
    monitor: { id: mid, name: nome, type: 'http', url: 'https://usuario:segredo@api.ficticio.example/saude?chave=abc' }, msg: `[${nome}] ${status === 0 ? 'Down' : 'Up'}` });
  const proj = (await api('GET', `/projects/by_slug?slug=${slug}`)).j;
  // 0. Diagnóstico antes: Beszel nunca enviou → telemetria indisponível (nunca "no ar")
  await p.goto('http://localhost:9000/vetor/monitoramento/'); await p.waitForSelector('#conectores .card');
  console.log('0. conectores antes →', (await p.$$eval('#conectores .card .chip', cs => cs.map(c => c.textContent))).join(' | '));
  console.log('   sem token →', await enviar('kuma', kuma(0, '09:00'), ''));
  // 1. Queda de um monitor desconhecido → triagem
  console.log('1. queda (desconhecido) →', await enviar('kuma', kuma(0, '09:00')));
  const rec = await esperar(async () => (await api('GET', '/vetor/recursos-monitorados?triagem=true')).j.find(r => r.id_externo === String(mid)));
  console.log('   em triagem →', rec ? `${rec.nome}, projeto: ${rec.projeto}` : 'NÃO');
  await p.reload(); await p.waitForSelector('#recursos tbody tr');
  await p.locator('#recursos tr', { hasText: nome }).locator('select').selectOption(String(proj.id)); await p.waitForTimeout(1500);
  console.log('   mapeado pela tela →', (await p.locator('#recursos tr', { hasText: nome }).locator('[role=status]').textContent()).trim());
  // 2. Alertas repetidos, evento fora de ordem e recuperação
  for (const hm of ['09:05', '09:10']) await enviar('kuma', kuma(0, hm));
  await enviar('kuma', kuma(1, '09:20'));
  await enviar('kuma', kuma(0, '09:15'));  // atrasado: anterior à recuperação
  const inc = await esperar(async () => { const l = (await api('GET', '/vetor/incidentes?estado=recuperado')).j.filter(i => i.recurso.nome === nome); return l.length && l; });
  const todos = (await api('GET', '/vetor/incidentes')).j.filter(i => i.recurso.nome === nome);
  console.log('2. incidentes do recurso →', todos.length, '| estado:', inc && inc[0].estado, '| alertas:', inc && inc[0].ocorrencias, '| demanda:', inc && inc[0].demanda ? `#${inc[0].demanda.ref} ${inc[0].demanda.assunto}` : '—');
  const det = (await api('GET', `/vetor/incidentes/${inc[0].id}`)).j;
  console.log('   linha do tempo →', det.linha_do_tempo.map(e => `${e.ocorrido_em.slice(11, 16)} ${e.status}`).join(', '));
  console.log('   payload sem credenciais → url_origem', det.linha_do_tempo[0].url_origem);
  const us = (await api('GET', `/userstories/by_ref?ref=${inc[0].demanda.ref}&project=${proj.id}`)).j;
  console.log('   demanda continua aberta →', !us.is_closed);
  await p.selectOption('#f-estado', ''); await p.waitForTimeout(800);
  await p.locator('#incidentes tr', { hasText: nome }).locator('button').click(); await p.waitForSelector('#linha-conteudo li');
  await p.screenshot({ path: `${out}/linha-do-tempo-1440.png` });
  await p.keyboard.press('Escape');
  // 3. Beszel: queda e volta de um servidor; alerta de CPU fica aberto
  const sys = `qa${mid}`, link = `https://beszel.ficticio.example/system/${sys}`;
  await enviar('beszel', { title: `Connection to [FICTÍCIO] web-${mid} is down 🔴`, message: `Connection to [FICTÍCIO] web-${mid} is down \n\n${link}` });
  await enviar('beszel', { title: `[FICTÍCIO] web-${mid} CPU above threshold`, message: `CPU averaged 94.20% for the previous 10 minutes.\n\n${link}` });
  await enviar('beszel', { title: `Connection to [FICTÍCIO] web-${mid} is up ✅`, message: `Connection to [FICTÍCIO] web-${mid} is up \n\n${link}` });
  const bz = await esperar(async () => { const l = (await api('GET', '/vetor/eventos-monitoramento?processamento=processado')).j.filter(e => e.id_recurso === sys); return l.length === 3 && l; });
  const recB = (await api('GET', '/vetor/recursos-monitorados?triagem=true')).j.find(r => r.id_externo === sys);
  console.log('3. Beszel →', bz ? `${bz.length} eventos processados` : 'NÃO', '| recurso em triagem:', recB ? recB.nome : 'não');
  const incB = (await api('GET', '/vetor/incidentes')).j.filter(i => i.recurso.nome.includes(`web-${mid}`));
  console.log('   incidentes →', incB.map(i => `${i.tipo}: ${i.estado}`).sort().join(', '), '| demanda (triagem):', incB.some(i => i.demanda) ? 'criada' : 'nenhuma');
  // 4. Painel: conectores, triagem, sem porcentagem
  await p.reload(); await p.waitForSelector('#conectores .card'); await p.waitForTimeout(800);
  console.log('4. conectores depois →', (await p.$$eval('#conectores .card .chip', cs => cs.map(c => c.textContent))).join(' | '));
  console.log('   alguma porcentagem de disponibilidade na tela?', /\d+([.,]\d+)?\s?%/.test(await p.textContent('main')));
  await p.locator('#t-conectores').scrollIntoViewIfNeeded();
  await p.screenshot({ path: `${out}/painel-1440.png` });
  const m = await (await b.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await m.goto('http://localhost:9000/login'); await m.fill('input[name=username]', user); await m.fill('input[name=password]', pw); await m.click('button[type=submit]'); await m.waitForURL(u => !u.pathname.startsWith('/login'));
  await m.goto('http://localhost:9000/vetor/monitoramento/'); await m.waitForSelector('#incidentes .card'); await m.waitForTimeout(800);
  console.log('5. celular → rolagem horizontal da página:', await m.evaluate(() => document.documentElement.scrollWidth > innerWidth));
  await m.screenshot({ path: `${out}/monitoramento-390.png` });
  console.log('recurso', nome);
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
