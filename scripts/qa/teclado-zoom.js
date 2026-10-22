// Teclado no login (ordem de foco, foco visível, Enter envia) e zoom 200% (1440 px a 2x = 720 px CSS).
const { chromium } = require('playwright');
(async () => {
  const [out, pw, slug] = process.argv.slice(2); const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  await p.goto('http://localhost:9000/login'); await p.waitForSelector('input[name=username]');
  const order = [];
  for (let i = 0; i < 4; i++) {
    await p.waitForTimeout(800);  // o tema anima o outline
    order.push(await p.evaluate(() => { const e = document.activeElement, s = getComputedStyle(e);
      return `${e.tagName.toLowerCase()}[${e.name || e.type || e.textContent.trim().slice(0, 20)}] outline=${s.outlineStyle} ${s.outlineWidth} ${s.outlineColor}`; }));
    await p.keyboard.press('Tab');
  }
  console.log('ordem de foco no login:\n  ' + order.join('\n  '));
  await p.focus('input[name=username]'); await p.keyboard.type('admin.dev'); await p.keyboard.press('Tab'); await p.keyboard.type(pw); await p.keyboard.press('Enter');
  await p.waitForURL(u => !u.pathname.startsWith('/login'), { timeout: 15000 }); console.log('Enter no formulário: logado em', new URL(p.url()).pathname);
  await p.keyboard.press('Tab'); await p.keyboard.press('Tab');
  await p.screenshot({ path: `${out}/foco-teclado-inicio-1440.png` });
  const z = await b.newContext({ viewport: { width: 720, height: 450 }, deviceScaleFactor: 2, storageState: await p.context().storageState() });
  const zp = await z.newPage();
  for (const [n, path] of [['quadro', `/project/${slug}/kanban`], ['card', `/project/${slug}/us/2`]]) {
    await zp.goto('http://localhost:9000' + path); await zp.waitForTimeout(3000);
    const overflow = await zp.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    await zp.screenshot({ path: `${out}/${n}-zoom200.png` }); console.log(`zoom 200% ${n}: rolagem horizontal da página = ${overflow}px`);
  }
  await b.close();
})().catch(e => { console.error(e.message); process.exit(1); });
