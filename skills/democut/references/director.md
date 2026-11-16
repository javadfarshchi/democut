# Director API (kit/director.mjs)

```js
import { chromium } from 'playwright';
import { Director } from '/abs/path/to/kit/director.mjs';

const browser = await chromium.launch();

// Optional: sign in once in an unrecorded context and save the session.
// const ctx = await browser.newContext(); ... log in ... await ctx.storageState({ path: 'auth.json' }); await ctx.close();

const d = await Director.open(browser, 'live', '.takes', {
  // view: { width: 1440, height: 810 },              // default; keep it unless you have a reason
  // mask: [['[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}', 'g', 'user@example.com'],
  //        ['acct_[A-Za-z0-9]+', 'g', 'acct_••••']],  // [regex, flags, replacement]; [] turns masking off
  // hide: ['#cookie-banner', '.dev-toolbar'],
  // storageState: 'auth.json',
});

await d.goto('http://localhost:3000/invoices');      // loads happen outside scenes, so they are cut

await d.scene('add-invoice', async () => {
  await d.click('text=New invoice');                 // glide, pause, ripple, click
  await d.type('#customer', 'Northwind');            // human-paced typing
  await d.press('Enter');
  await d.zoom('.invoice-preview', { fill: 0.6 });   // eased camera move, applied in the edit
  await d.hold(1200);                                // let the narration land
});                                                  // zoom resets at scene end

await d.close();                                     // writes live.webm + live.timeline.json
await browser.close();
```

| Method | Notes |
|---|---|
| `Director.open(browser, take, outDir, opts)` | One take = one video. Options: `view`, `mask`, `hide`, `accent`, `storageState`. |
| `scene(id, fn)` | Marks a shot. Scenes cannot nest. |
| `goto(url)` | Navigate and wait for network idle. Use between scenes. |
| `click(target, {ms, settle})` | `target` is a selector string or a Playwright Locator. |
| `type(target, text, {delay})` | Clicks the field, then types. |
| `hover(target)`, `press(key)`, `scroll(dy)` | Scroll is eased; it ends any zoom first. |
| `zoom(target, {fill, max, hold})` | Zooms so the target fills `fill` of the frame, capped at `max` (1.6). |
| `unzoom(holdMs)` | Zoom back out inside a scene. |
| `spotlight(target, on)` | Outline an element. |
| `hold(ms)` | Wait while recording. |
| `page` | The Playwright Page, for anything else (fill fields off camera, route mocks, evaluate). |

## Stubbing data

Use `d.page.route('**/api/**', ...)` before `goto` to serve test data, and give that take a `STUBBED` badge.

## Terminal shots

`kit/terminal.html?src=session.json` replays a CLI session (typed commands and their output) in the browser:

```js
await d.goto(`${BASE}/kit/terminal.html?src=/session.json`);   // serve kit/ and session.json over http
await d.page.evaluate(() => window.democutReady);
await d.scene('install', () => d.page.evaluate(() => window.democutStep(0)));
```

Paste real output into `session.json`; mark any shortening on screen (for example `# ... 9 more lines`).
