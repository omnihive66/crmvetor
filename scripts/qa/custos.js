// SPEC-09 pela interface: estimativa (R$ 70), orçamento × realizado (+R$ 20 / +20%), importação sem duplicar, rateio e permissão.
// Uso: node custos.js <saida> <admin> <senha> <outro-usuario> <senha> <nome-do-cliente>
const fs = require('fs');
const { chromium } = require('playwright');
(async () => {
  const [out, user, pw, outro, outroPw, nomeCliente] = process.argv.slice(2);
  const b = await chromium.launch();
  const entrar = async (u, s, viewport = { width: 1440, height: 900 }) => {
    const p = await (await b.newContext({ viewport, acceptDownloads: true })).newPage();
    await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
    await p.fill('input[name=username]', u); await p.fill('input[name=password]', s); await p.click('button[type=submit]'); await p.waitForURL(x => !x.pathname.startsWith('/login'));
    const t = await p.evaluate(() => JSON.parse(localStorage.getItem('token')));
    p.api = (m, url, d) => p.evaluate(async ([m, url, d, t]) => { const r = await fetch('/api/v1' + url, { method: m, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: d ? JSON.stringify(d) : undefined }); return { s: r.status, j: await r.json().catch(() => null) }; }, [m, url, d, t]);
    return p;
  };
  let p = await entrar(user, pw);
  const pessoas = (await p.api('GET', '/vetor/perfis?page_size=100')).j;
  const eu = pessoas.find(x => x.username === user), ele = pessoas.find(x => x.username === outro);
  await p.api('PATCH', `/vetor/perfis/${eu.id}`, { ver_custos: true });  // a permissão financeira é explícita, até para o Administrador
  await p.close(); p = await entrar(user, pw);
  const cliente = (await p.api('GET', `/vetor/clientes?q=${encodeURIComponent(nomeCliente)}`)).j[0];
  const mes = new Date().toISOString().slice(0, 7);
  // 1. Estimativa pela aba Custos do cliente
  await p.goto(`http://localhost:9000/vetor/clientes/cliente.html?id=${cliente.id}&aba=custos`); await p.waitForSelector('#painel h3');
  const nome = `[FICTÍCIO] Hospedagem ${Date.now() % 100000}`;
  await p.fill('#painel input[name=nome]', nome); await p.click('text=Criar estimativa'); await p.waitForTimeout(1200);
  await p.selectOption('#painel select[aria-label="Estimativa e versão"]', { label: `${nome} · v1` }); await p.waitForSelector('#painel form [name=categoria]');
  const add = async (natureza, campos) => {
    await p.selectOption('#painel select[name=natureza]', natureza);
    for (const [k, v] of Object.entries(campos)) await p.fill(`#painel form [name=${k}]`, v);
    await p.click('text=Adicionar item'); await p.waitForTimeout(900);
  };
  await add('variavel', { categoria: 'armazenamento', quantidade: '100', unidade: 'GB', preco_unitario: '0,20' });
  await add('fixo', { categoria: 'suporte', quantidade: '1', unidade: 'mês', preco_unitario: '50' });
  await add('ajuste', { categoria: 'impostos', percentual: '10', preco_unitario: '0', quantidade: '1', unidade: '' });
  const linha = (await p.locator('#painel table', { hasText: 'Antes de ajustes' }).locator('tbody tr').first().textContent()).replace(/\s+/g, ' ');
  console.log('1. totais (Custo mensal) →', linha);
  await p.screenshot({ path: `${out}/estimativa-1440.png` });
  // 2. Orçamento 100 e realizado 120 no mês
  await p.fill('#painel form [name=valor]', '100'); await p.click('text=Salvar orçamento'); await p.waitForTimeout(1200);
  const formsValor = p.locator('#painel form', { hasText: 'Lançar realizado' });
  await formsValor.locator('[name=categoria]').fill('infra'); await formsValor.locator('[name=valor]').fill('120'); await p.click('text=Lançar realizado'); await p.waitForTimeout(1500);
  console.log('2. comparação →', (await p.locator('#painel .card', { hasText: 'Orçamento' }).first().textContent()).replace(/\s+/g, ' ').trim());
  await p.locator('#painel h3', { hasText: 'Orçamento' }).scrollIntoViewIfNeeded();
  await p.screenshot({ path: `${out}/orcamento-realizado-1440.png` });
  // 3. Página Custos: importar CSV duas vezes, não alocados, rateio
  const csv = `${process.env.SCRATCH}/qa-custos.csv`;
  fs.writeFileSync(csv, `id;periodo;categoria;descricao;valor;moeda;cliente;parcial\nq1;${mes};cluster;[FICTÍCIO] Kubernetes compartilhado;300,00;BRL;;sim\nq2;${mes};infra;[FICTÍCIO] VM dedicada;45,50;BRL;${cliente.id};não\n`);
  await p.goto('http://localhost:9000/vetor/custos/'); await p.waitForSelector('#imp');
  const lote = `qa-${Date.now() % 100000}`;
  for (const i of [1, 2]) {
    await p.fill('#imp [name=lote]', lote); await p.setInputFiles('#imp [name=arquivo]', csv); await p.click('#imp button[type=submit]'); await p.waitForTimeout(1200);
    console.log(`3. importação ${i} →`, await p.textContent('#imp-msg'));
  }
  console.log('   não alocados →', (await p.textContent('#nao')).replace(/\s+/g, ' ').trim());
  await p.fill('#rat [name=categoria]', 'cluster'); await p.fill('#rat [name=partes]', `${cliente.nome} = 100`); await p.click('text=Salvar regra'); await p.waitForTimeout(1200);
  console.log('   rateio →', await p.textContent('#rat-msg'), '| não alocados depois →', (await p.textContent('#nao')).replace(/\s+/g, ' ').trim());
  await p.screenshot({ path: `${out}/pagina-custos-1440.png` });
  const orc = (await p.api('GET', `/vetor/custos/orcamentos?cliente=${cliente.id}`)).j.find(o => o.periodo.startsWith(mes));
  const comp = (await p.api('GET', `/vetor/custos/orcamentos/${orc.id}/comparacao`)).j;
  console.log('   comparação com rateio e importação →', `realizado ${comp.realizado}, diferença ${comp.diferenca}, ${comp.percentual}%`, '|', comp.aviso_parcial);
  const dl = await Promise.all([p.waitForEvent('download'), p.click('#exportar')]);
  console.log('4. exportação →', dl[0].suggestedFilename());
  // 5. Sem permissão financeira: sem menu, sem aba, API 403
  await p.api('PATCH', `/vetor/perfis/${ele.id}`, { ver_custos: false });
  const q = await entrar(outro, outroPw);
  await q.goto(`http://localhost:9000/vetor/clientes/cliente.html?id=${cliente.id}`); await q.waitForSelector('.abas'); await q.waitForTimeout(800);
  console.log('5. sem permissão → aba Custos:', await q.$('#aba-custos') ? 'APARECE' : 'não aparece', '| menu Custos:', await q.$('.vt-shell a[href$="vetor/custos/"]') ? 'APARECE' : 'não aparece',
    '| API:', (await q.api('GET', `/vetor/custos/realizados?cliente=${cliente.id}`)).s, '| exportação:', (await q.api('GET', '/vetor/custos/realizados/exportar')).s);
  await q.goto('http://localhost:9000/vetor/custos/'); await q.waitForTimeout(800);
  console.log('   página Custos →', (await q.textContent('main')).trim());
  await p.api('PATCH', `/vetor/perfis/${ele.id}`, { ver_custos: ele.ver_custos });  // volta como estava
  fs.unlinkSync(csv);
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
