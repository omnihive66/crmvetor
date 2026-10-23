// SPEC-10: linha de base de desempenho. Listas de 50 itens, p95 da API pelo gateway (sem chamadas externas).
// Uso: node desempenho.js <usuario> <senha>. Cria (uma vez) 50 clientes e 50 demandas [FICTÍCIO] de carga.
const { performance } = require('perf_hooks');
(async () => {
  const [user, pw] = process.argv.slice(2), B = 'http://localhost:9000/api/v1';
  const auth = await (await fetch(`${B}/auth`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type: 'normal', username: user, password: pw }) })).json();
  const h = { 'Content-Type': 'application/json', Authorization: `Bearer ${auth.auth_token}` };
  const api = async (m, url, d) => { const r = await fetch(B + url, { method: m, headers: h, body: d ? JSON.stringify(d) : undefined }); return r.json().catch(() => null); };
  // Dataset de carga
  const clientes = await api('GET', '/vetor/clientes?q=Carga&page_size=100');
  for (let i = clientes.length; i < 50; i++) await api('POST', '/vetor/clientes', { nome: `[FICTÍCIO] Carga ${String(i + 1).padStart(2, '0')}`, confirmar_duplicado: true });
  let proj = (await api('GET', '/projects?slug=')).find?.(p => p.name === '[FICTÍCIO] Carga de desempenho');
  if (!proj) proj = await api('POST', '/projects', { name: '[FICTÍCIO] Carga de desempenho', description: 'linha de base SPEC-10', creation_template: 1001 });
  const us = await api('GET', `/userstories?project=${proj.id}&page_size=500`);  // contagem sem a paginação padrão de 30
  for (let i = us.length; i < 50; i++) await api('POST', '/userstories', { project: proj.id, subject: `[FICTÍCIO] Demanda de carga ${i + 1}`, assigned_to: auth.id });
  const alvos = {
    'clientes (50)': '/vetor/clientes?q=Carga&page_size=50',
    'demandas entre projetos (50)': `/vetor/demandas?projeto=${proj.id}&page_size=50`,
    'histórias do projeto, Taiga (50)': `/userstories?project=${proj.id}&page_size=50`,
    'busca global': '/vetor/busca?q=Carga',
  };
  const N = 40, linhas = [];
  for (const [nome, url] of Object.entries(alvos)) {
    let itens = 0;
    for (let i = 0; i < 5; i++) await fetch(B + url, { headers: h });  // aquecimento
    const t = [];
    for (let i = 0; i < N; i++) {
      const ini = performance.now(); const r = await fetch(B + url, { headers: h }); const corpo = await r.json(); t.push(performance.now() - ini);
      itens = Array.isArray(corpo) ? corpo.length : Object.values(corpo).flat().length;
    }
    t.sort((a, b) => a - b);
    const q = f => t[Math.min(t.length - 1, Math.ceil(f * t.length) - 1)].toFixed(0);
    linhas.push({ nome, itens, p50: q(0.5), p95: q(0.95), max: t[t.length - 1].toFixed(0) });
  }
  console.log(`requisições sequenciais por lista: ${N} (após 5 de aquecimento), pelo gateway local, sem chamadas externas`);
  console.log('lista | itens | p50 ms | p95 ms | máx ms | meta p95 < 800 ms');
  for (const l of linhas) console.log(`${l.nome} | ${l.itens} | ${l.p50} | ${l.p95} | ${l.max} | ${Number(l.p95) < 800 ? 'dentro' : 'FORA'}`);
})().catch(e => { console.error(e.message); process.exit(1); });
