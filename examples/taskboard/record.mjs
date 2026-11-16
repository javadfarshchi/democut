// Records the takes for the democut self-demo. Run from the repo root:  node examples/taskboard/record.mjs [outDir]
// Serves the repo over a local static server, so the sample app and the kit's terminal page load from localhost.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { Director } from '../../skills/democut/kit/director.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const OUT = path.resolve(process.argv[2] || '.takes');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css' };

const server = http.createServer((req, res) => {
  const p = path.join(ROOT, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': TYPES[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
});
await new Promise((r) => server.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${server.address().port}`;
const APP = `${BASE}/examples/taskboard/app/index.html`;

const browser = await chromium.launch();
// Mask emails with a visible placeholder, so the masking is obvious on screen.
const mask = [['[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}', 'g', '••••@••••']];

// ---- take "app": the sample app, recorded like a presenter would show it
{
  const d = await Director.open(browser, 'app', OUT, { mask });
  await d.goto(APP);
  await d.scene('board', async () => {
    await d.hold(600);
    await d.hover('.col[data-col="todo"] .card >> nth=1');
    await d.hover('.col[data-col="doing"] .card >> nth=0');
    await d.hover('.col[data-col="done"] .card >> nth=0');
    await d.hold(500);
  });
  await d.scene('search', async () => {
    await d.type('#search', 'login');
    await d.zoom('.col[data-col="todo"]', { fill: 0.7 });
    await d.hold(900);
  });
  await d.page.fill('#search', '');
  await d.page.dispatchEvent('#search', 'input');
  await d.scene('add-task', async () => {
    await d.click('#add');
    await d.type('#title', 'Record the launch demo');
    await d.page.selectOption('#prio', 'high');
    await d.click('#save', { settle: 400 });
    await d.zoom('.col[data-col="todo"] .card >> nth=0', { fill: 0.45 });
    await d.hold(1200);
  });
  await d.scene('open-task', async () => {
    await d.click('.col[data-col="todo"] .card >> nth=0', { settle: 900 });
    await d.zoom('#panel', { fill: 0.75 });
    await d.unzoom(500);
    await d.click('#to-done', { settle: 1400 });
  });
  await d.scene('mask', async () => {
    await d.hover('.who');
    await d.zoom('.who', { fill: 0.4, max: 1.8 });
    await d.hold(1800);
  });
  await d.close();
}

// ---- take "insights": same app, made-up chart data, so it gets its own badge
{
  const d = await Director.open(browser, 'insights', OUT, { mask });
  await d.goto(APP);
  await d.scene('insights', async () => {
    await d.click('#nav-stats', { settle: 600 });
    await d.zoom('#chart', { fill: 0.75 });
    await d.hold(1600);
  });
  await d.close();
}

// ---- take "terminal": the two commands that made this video, replayed from session.json
{
  const d = await Director.open(browser, 'terminal', OUT, { mask: [] });
  await d.goto(`${BASE}/skills/democut/kit/terminal.html?src=/examples/taskboard/session.json`);
  await d.page.evaluate(() => window.democutReady);
  await d.scene('record', async () => { await d.page.evaluate(() => window.democutStep(0)); await d.hold(400); });
  await d.scene('build', async () => { await d.page.evaluate(() => window.democutStep(1)); await d.hold(800); });
  await d.close();
}

await browser.close();
server.close();
console.log(`takes written to ${OUT}`);
