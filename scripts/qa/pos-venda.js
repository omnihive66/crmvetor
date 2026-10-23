// SPEC-08 pela interface: aba Operação do cliente (relacionamento, disponibilidade, infraestrutura e adoção separados).
// Uso: node pos-venda.js <saida> <usuario> <senha> <nome-do-cliente> <slug-do-projeto>
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw, nomeCliente, slug] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  await p.fill('input[name=username]', user); await p.fill('input[name=password]', pw); await p.click('button[type=submit]'); await p.waitForURL(u => !u.pathname.startsWith('/login'));
  const token = await p.evaluate(() => JSON.parse(localStorage.getItem('token')));
  const api = (m, url, d) => p.evaluate(async ([m, url, d, t]) => { const r = await fetch('/api/v1' + url, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: d ? JSON.stringify(d) : undefined }); return { s: r.status, j: await r.json().catch(() => null) }; }, [m, url, d, token]);
  const cliente = (await api('GET', `/vetor/clientes?q=${encodeURIComponent(nomeCliente)}`)).j[0];
  const proj = (await api('GET', `/projects/by_slug?slug=${slug}`)).j;
  const url = `http://localhost:9000/vetor/clientes/cliente.html?id=${cliente.id}&aba=operacao`;
  // 0. Infraestrutura: mapear um servidor do Beszel (em triagem desde a SPEC-07) para o projeto do cliente
  for (const r of (await api('GET', '/vetor/recursos-monitorados?triagem=true')).j.filter(r => r.provedor === 'beszel'))
    await api('PATCH', `/vetor/recursos-monitorados/${r.id}`, { projeto: proj.id });
  // 1. Antes da telemetria: adoção sem dados
  await p.goto(url); await p.waitForSelector('section[aria-label="Adoção"]');
  console.log('1. adoção antes →', (await p.textContent('section[aria-label="Adoção"] p.vt-meta:nth-of-type(2)')).trim());
  // 2. Próximo contato pelo formulário do Resumo
  await p.goto(url.replace('aba=operacao', 'aba=resumo')); await p.click('text=Editar dados');
  await p.fill('input[name=proximo_contato]', '2026-11-05'); await p.click('button[type=submit]'); await p.waitForTimeout(1000);
  console.log('2. próximo contato salvo →', (await api('GET', `/vetor/clientes/${cliente.id}`)).j.proximo_contato);
  // 3. Produto com telemetria (sintético) pela tela do Administrador; o token aparece uma vez
  await p.goto(url); await p.waitForSelector('section[aria-label="Adoção"] summary');
  await p.click('section[aria-label="Adoção"] summary');
  const chave = `erp-${Date.now() % 100000}`;
  await p.fill('section[aria-label="Adoção"] input[name=nome]', '[FICTÍCIO] ERP Web'); await p.fill('section[aria-label="Adoção"] input[name=chave]', chave);
  await p.check('section[aria-label="Adoção"] input[name=sintetico]'); await p.click('text=Gerar token de ingestão');
  await p.waitForSelector('section[aria-label="Adoção"] p.pre');
  const tok = (await p.textContent('section[aria-label="Adoção"] p.pre')).trim();
  console.log('3. token gerado →', tok.slice(0, 5) + '…');
  // 4. O "produto" envia eventos sintéticos pseudonimizados
  const h = n => new Date(Date.now() - n * 3600e3).toISOString();
  const eventos = [{ id: `${chave}-1`, tipo: 'login', usuario: 'pseud-0001', ocorrido_em: h(5) },
    { id: `${chave}-2`, tipo: 'atividade', funcionalidade: 'emitir_nota', usuario: 'pseud-0001', ocorrido_em: h(5) },
    { id: `${chave}-3`, tipo: 'atividade', funcionalidade: 'relatorio_vendas', usuario: 'pseud-0002', ocorrido_em: h(30) },
    { id: `${chave}-4`, tipo: 'login', usuario: 'pseud-0003', ocorrido_em: h(48) }, { id: `${chave}-5`, tipo: 'pulso', ocorrido_em: h(1) }];
  const envio = await p.evaluate(async ([ev, t]) => { const r = await fetch('/api/v1/vetor/uso/eventos', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Produto ' + t }, body: JSON.stringify({ eventos: ev }) }); return `${r.status} ${await r.text()}`; }, [eventos, tok]);
  console.log('4. ingestão →', envio);
  const conteudo = await p.evaluate(async t => { const r = await fetch('/api/v1/vetor/uso/eventos', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Produto ' + t }, body: JSON.stringify({ eventos: [{ id: 'x', tipo: 'atividade', funcionalidade: 'chat', usuario: 'pseud-0009', ocorrido_em: new Date().toISOString(), mensagem: 'texto do usuário' }] }) }); return r.status; }, tok);
  console.log('   evento com conteúdo (mensagem) →', conteudo);
  // 5. Painel: quatro blocos
  await p.goto(url); await p.waitForSelector('section[aria-label="Adoção"] dl'); await p.waitForTimeout(500);
  for (const s of ['Relacionamento', 'Disponibilidade do produto', 'Infraestrutura', 'Adoção']) {
    console.log(`5. ${s} →`, (await p.textContent(`section[aria-label="${s}"]`)).replace(/\s+/g, ' ').replace(/Adicionar produto.*$/, '').trim().slice(0, 260));
  }
  console.log('   nota única de saúde na tela?', /saúde\s*:?\s*\d|score|nota\s+\d/i.test(await p.textContent('#painel')));
  await p.screenshot({ path: `${out}/operacao-1440.png` });
  // 6. "abrir ata" leva à reunião
  await p.click('section[aria-label="Relacionamento"] a:has-text("abrir ata")'); await p.waitForTimeout(800);
  const alvo = new URL(p.url()).hash;
  console.log('6. abrir ata →', p.url().includes('aba=reunioes'), alvo, '| elemento existe:', !!(alvo && await p.$(alvo)));
  // 7. Celular
  const m = await (await b.newContext({ viewport: { width: 390, height: 844 } })).newPage();
  await m.goto('http://localhost:9000/login'); await m.fill('input[name=username]', user); await m.fill('input[name=password]', pw); await m.click('button[type=submit]'); await m.waitForURL(u => !u.pathname.startsWith('/login'));
  await m.goto(url); await m.waitForSelector('section[aria-label="Adoção"] dl'); await m.waitForTimeout(500);
  console.log('7. celular → rolagem horizontal da página:', await m.evaluate(() => document.documentElement.scrollWidth > innerWidth));
  await m.screenshot({ path: `${out}/operacao-390.png` });
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
