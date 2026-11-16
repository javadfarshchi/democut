// democut director: records a Playwright session the way a person would present it.
//
// - a visible cursor that glides between targets with an ease-out curve
// - a ripple on every click, and a short hold before it so viewers can follow
// - typed input at a human pace
// - named scenes, so the editor can cut out page loads and time each shot to its narration
// - zoom marks (the box of the element to zoom onto), applied smoothly later in the edit
// - masking: text that matches your patterns (emails by default) is replaced before it is painted
//
// MIT licence. See ../../../LICENSE.
import fs from 'node:fs';
import path from 'node:path';

export const DEFAULT_VIEW = { width: 1440, height: 810 };

/** Runs inside every page before any of its scripts. Kept self-contained: it is serialised by Playwright. */
function pageKit(opts) {
  const patterns = (opts.mask || []).map(([src, flags, repl]) => [new RegExp(src, flags), repl]);
  const hide = (opts.hide || []).join(',');
  const scrub = (root) => {
    if (!patterns.length || !root) return;
    const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walk.nextNode())) {
      let v = node.nodeValue || '';
      let changed = false;
      for (const [re, repl] of patterns) {
        re.lastIndex = 0;
        if (re.test(v)) { re.lastIndex = 0; v = v.replace(re, repl); changed = true; }
      }
      if (changed) node.nodeValue = v;
    }
    if (root.querySelectorAll) {
      root.querySelectorAll('input,textarea').forEach((el) => {
        for (const [re, repl] of patterns) { re.lastIndex = 0; if (re.test(el.value)) { re.lastIndex = 0; el.value = el.value.replace(re, repl); } }
      });
    }
  };
  const css = `
    #dc-cursor{position:fixed;left:0;top:0;width:28px;height:28px;z-index:2147483647;pointer-events:none;
      transform:translate(-4px,-3px);filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))}
    .dc-ripple{position:fixed;width:18px;height:18px;margin:-9px 0 0 -9px;border-radius:50%;z-index:2147483646;
      pointer-events:none;border:3px solid ${opts.accent};background:${opts.accent}33;animation:dc-ripple .55s ease-out forwards}
    @keyframes dc-ripple{to{transform:scale(4);opacity:0}}
    .dc-spot{outline:3px solid ${opts.accent}!important;outline-offset:4px!important;border-radius:6px}
    ${hide ? `${hide}{display:none!important}` : ''}
  `;
  const boot = () => {
    if (document.getElementById('dc-cursor')) return;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
    const c = document.createElement('div');
    c.id = 'dc-cursor';
    c.innerHTML = '<svg viewBox="0 0 24 24" width="28" height="28"><path d="M4 2l15 10.5-6.6 1.3 3.9 7.4-2.7 1.4-3.9-7.5L4 20z" fill="#111827" stroke="#fff" stroke-width="1.4" stroke-linejoin="round"/></svg>';
    const p = window.__dcPos || { x: opts.width / 2, y: opts.height / 2 };
    c.style.left = p.x + 'px';
    c.style.top = p.y + 'px';
    document.body.appendChild(c);
    scrub(document.body);
    new MutationObserver((muts) => muts.forEach((m) => {
      if (m.type === 'characterData') scrub(m.target.parentNode);
      m.addedNodes.forEach((n) => scrub(n.nodeType === 3 ? n.parentNode : n));
    })).observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
  window.__dcMove = (x, y) => {
    window.__dcPos = { x, y };
    const c = document.getElementById('dc-cursor');
    if (c) { c.style.left = x + 'px'; c.style.top = y + 'px'; }
  };
  window.__dcRipple = (x, y) => {
    const r = document.createElement('div');
    r.className = 'dc-ripple';
    r.style.left = x + 'px';
    r.style.top = y + 'px';
    document.body.appendChild(r);
    setTimeout(() => r.remove(), 700);
  };
}

const EMAIL = ['[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}', 'g', 'user@example.com'];

export class Director {
  /**
   * Open a recording. Each Director writes one take: <outDir>/<name>.webm and <name>.timeline.json.
   * @param {import('playwright').Browser} browser
   * @param {string} name   take name, referenced by the storyboard ("take")
   * @param {string} outDir where takes go
   * @param {object} [o]
   * @param {{width:number,height:number}} [o.view]  viewport (CSS px). Playwright video ignores deviceScaleFactor.
   * @param {Array<[string,string,string]>} [o.mask] [regex source, flags, replacement]; emails are masked by default
   * @param {string[]} [o.hide] CSS selectors hidden during recording (dev toolbars, cookie banners)
   * @param {string} [o.accent] ripple / spotlight colour
   * @param {string} [o.storageState] Playwright storage state file, e.g. a signed-in session saved outside the recording
   */
  static async open(browser, name, outDir, o = {}) {
    const view = o.view || DEFAULT_VIEW;
    fs.mkdirSync(outDir, { recursive: true });
    const rawDir = path.join(outDir, `.raw-${name}`);
    const context = await browser.newContext({
      viewport: view,
      deviceScaleFactor: 1,
      recordVideo: { dir: rawDir, size: view },
      ...(o.storageState ? { storageState: o.storageState } : {}),
    });
    await context.addInitScript(pageKit, {
      mask: o.mask === undefined ? [EMAIL] : o.mask,
      hide: o.hide || [],
      accent: o.accent || '#2563eb',
      width: view.width,
      height: view.height,
    });
    const page = await context.newPage();
    const d = new Director(page, context, name, outDir, view, rawDir);
    return d;
  }

  constructor(page, context, name, outDir, view, rawDir) {
    Object.assign(this, { page, context, name, outDir, view, rawDir });
    this.t0 = Date.now();
    this.marks = [];
    this.zooms = [];
    this.pos = { x: view.width / 2, y: view.height / 2 };
    this.zoomed = false;
    this.open = null;
  }

  /** Seconds since the take started. */
  now() { return (Date.now() - this.t0) / 1000; }
  hold(ms) { return this.page.waitForTimeout(ms); }

  /** Everything inside body() becomes one shot named `id`. Time outside scenes is cut. */
  async scene(id, body) {
    if (this.open) throw new Error(`scene "${id}" started inside "${this.open}"`);
    this.open = id;
    this.marks.push({ scene: id, at: this.now(), kind: 'start' });
    try { await body(); } finally {
      await this.unzoom(0);
      this.marks.push({ scene: id, at: this.now(), kind: 'end' });
      this.open = null;
    }
  }

  /** Navigate and wait for the page to settle. Call it outside a scene so the load is cut. */
  async goto(url, { settle = 400 } = {}) {
    await this.unzoom(0);
    await this.page.goto(url);
    await this.page.waitForLoadState('networkidle').catch(() => {});
    await this.page.evaluate(({ x, y }) => window.__dcMove?.(x, y), this.pos);
    await this.hold(settle);
  }

  async #point(target) {
    const t = typeof target === 'string' ? this.page.locator(target).first() : target.first();
    await t.scrollIntoViewIfNeeded().catch(() => {});
    const b = await t.boundingBox();
    if (!b) throw new Error(`target has no box: ${target}`);
    return { t, x: b.x + Math.min(b.width / 2, 60), y: b.y + b.height / 2 };
  }

  async #glide(x, y, ms) {
    const from = { ...this.pos };
    const steps = Math.max(12, Math.round(ms / 16));
    for (let i = 1; i <= steps; i++) {
      const k = i / steps;
      const e = 1 - Math.pow(1 - k, 3);
      const px = from.x + (x - from.x) * e;
      const py = from.y + (y - from.y) * e;
      await this.page.mouse.move(px, py);
      await this.page.evaluate(([a, b]) => window.__dcMove?.(a, b), [px, py]);
      await this.page.waitForTimeout(ms / steps);
    }
    this.pos = { x, y };
  }

  /** Move the cursor to a target (selector or Locator). */
  async hover(target, { ms = 750 } = {}) {
    const p = await this.#point(target);
    await this.#glide(p.x, p.y, ms);
    await this.hold(250);
  }

  /** Glide, pause, ripple, click. */
  async click(target, { ms = 750, settle = 700 } = {}) {
    const p = await this.#point(target);
    await this.#glide(p.x, p.y, ms);
    await this.hold(280);
    await this.page.evaluate(([a, b]) => window.__dcRipple?.(a, b), [p.x, p.y]);
    await this.hold(120);
    await p.t.click();
    await this.hold(settle);
  }

  /** Click a field and type into it at a human pace. */
  async type(target, text, { delay = 75 } = {}) {
    await this.click(target, { settle: 200 });
    const p = await this.#point(target);
    await p.t.pressSequentially(text, { delay });
    await this.hold(450);
  }

  async press(key, { settle = 500 } = {}) {
    await this.page.keyboard.press(key);
    await this.hold(settle);
  }

  /** Eased scroll by dy CSS pixels. Do not scroll while zoomed. */
  async scroll(dy, { ms = 1100 } = {}) {
    await this.unzoom(300);
    const steps = Math.round(ms / 16);
    let done = 0;
    for (let i = 1; i <= steps; i++) {
      const k = i / steps;
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      const want = Math.round(dy * e);
      await this.page.mouse.wheel(0, want - done);
      done = want;
      await this.page.waitForTimeout(ms / steps);
    }
    await this.hold(300);
  }

  /**
   * Camera move onto `target`, applied in the edit: the frame eases in until the target fills about `fill` of it.
   * Recorded as a mark; nothing changes in the page. Zoom ends at unzoom(), the next scroll/goto, or scene end.
   */
  async zoom(target, { fill = 0.6, max = 1.6, hold = 1100 } = {}) {
    const t = typeof target === 'string' ? this.page.locator(target).first() : target.first();
    await t.scrollIntoViewIfNeeded({ timeout: 5000 }).catch(() => {});
    await this.hold(150);
    const b = await t.boundingBox({ timeout: 5000 }).catch(() => null);
    if (!b) { console.warn(`[democut] zoom target not found in take ${this.name}`); return; }
    const s = Math.max(1.15, Math.min(max, (this.view.width * fill) / b.width, (this.view.height * fill) / b.height));
    this.zooms.push({ at: this.now(), kind: 'in', scale: +s.toFixed(3), cx: b.x + b.width / 2, cy: b.y + b.height / 2 });
    this.zoomed = true;
    await this.hold(hold);
  }

  async unzoom(holdMs = 900) {
    if (!this.zoomed) return;
    this.zooms.push({ at: this.now(), kind: 'out', scale: 1, cx: this.view.width / 2, cy: this.view.height / 2 });
    this.zoomed = false;
    if (holdMs) await this.hold(holdMs);
  }

  /** Outline an element (on) or remove the outline (off). */
  async spotlight(target, on = true) {
    const t = typeof target === 'string' ? this.page.locator(target).first() : target.first();
    await t.evaluate((e, v) => e.classList.toggle('dc-spot', v), on);
  }

  /** Finish the take: writes <name>.webm and <name>.timeline.json. */
  async close() {
    const video = this.page.video();
    await this.context.close();
    const out = path.join(this.outDir, `${this.name}.webm`);
    if (video) fs.renameSync(await video.path(), out);
    fs.rmSync(this.rawDir, { recursive: true, force: true });
    fs.writeFileSync(
      path.join(this.outDir, `${this.name}.timeline.json`),
      JSON.stringify({ view: this.view, marks: this.marks, zooms: this.zooms }, null, 1),
    );
    const n = this.marks.filter((m) => m.kind === 'start').length;
    console.log(`[democut] take ${this.name}: ${n} scene${n === 1 ? '' : 's'}, ${this.now().toFixed(1)}s -> ${out}`);
    return out;
  }
}
