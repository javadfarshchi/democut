<div align="center">

# democut

**Narrated product demo videos, written as code.**

Your coding agent records the real app in a browser. democut edits it into a captioned, narrated demo
with zooms, chapters, a short cut, a GIF and a player page. Offline voice. No Remotion. MIT.

<a href="https://javadfarshchi.github.io/democut/"><img src="docs/demo.gif" alt="democut demo: a sample app recorded with cursor, click ripples, zooms and captions" width="820"></a>

[**▶ Watch the full demo with chapters and transcript**](https://javadfarshchi.github.io/democut/) · made by democut, of course

</div>

## Install

**Claude Code** (plugin):

```
/plugin marketplace add javadfarshchi/democut
/plugin install democut@democut
```

**Any agent that reads SKILL.md** (Claude Code, Codex, Cursor, Gemini CLI, Copilot, ...):

```bash
npx skills add javadfarshchi/democut
```

Or copy `skills/democut/` into your agent's skills folder (for Claude Code: `~/.claude/skills/democut`).

Then ask your agent: *"Make a 2-minute demo video of our signup flow, plus a 30-second cut for the README."*

**Prerequisites:** Node 18+, Python 3.10+, ffmpeg on PATH.

```bash
npm i -D playwright && npx playwright install chromium
pip install -r requirements.txt
bash skills/democut/kit/get-voice.sh       # offline Kokoro voice, ~120 MB, once
```

## What you get

From one `storyboard.json`, for every cut you define:

| Output | |
|---|---|
| `full.mp4`, `short.mp4` | 1080p30, H.264 + AAC, MP4 chapters, loudness-normalised narration |
| `*.srt`, `*.vtt` | Captions, also burned into the video for muted viewing |
| `index.html` | Self-contained player: cut switcher, clickable chapters, live transcript |
| `short.gif` | Palette-optimised GIF for your README |
| `contact-sheet.png` | One frame per shot, so you (or your agent) can review the edit at a glance |

What the video looks like:

- **A cursor people can follow:** eased glides, a pause before each click, click ripples, human-paced typing.
- **Camera moves:** smooth zooms onto the element that matters, measured from the DOM, applied in the edit.
- **Tight pacing:** page loads are cut, slow parts are sped up (max 1.7x), each shot lasts as long as its narration.
- **Honest badges:** every shot says where it came from (`LIVE`, `STUBBED`, `SAMPLE DATA`, `TERMINAL`, ...).
- **Privacy by default:** emails (and any pattern you add) are replaced in the DOM before they are painted, so
  they never reach the raw video.
- **Polish:** chapter cards, a framed app window on a gradient backdrop, crossfades, caption chunks of about a dozen
  words, optional caveat banners.
- **Terminal shots:** replay a CLI session in the browser so it matches the rest of the video.

## How it works

```
recording script (Playwright + Director)  ──►  <take>.webm + <take>.timeline.json   (scenes, zooms)
storyboard.json  (shots, narration, cuts)  ──►  build.py  ──►  mp4 · srt · vtt · gif · player page
```

1. **Record.** A short script drives the app with `Director` (`click`, `type`, `zoom`, `scene`). Everything inside
   `d.scene('id', ...)` becomes a shot; everything outside it is cut.
2. **Storyboard.** Shots in order, chapter cards, narration per shot, and which shots make each cut.
3. **Build.** `build.py` voices each line, times each shot to it, zooms, frames, captions, mixes and packages.

The agent skill (`skills/democut/SKILL.md`) walks your agent through the whole thing: story first, honest
badges, a cheap silent draft with a contact sheet to review, then the final build.

### Try the example

```bash
git clone https://github.com/javadfarshchi/democut && cd democut
npm i && npx playwright install chromium && pip install -r requirements.txt && bash skills/democut/kit/get-voice.sh
npm run example:record     # records .takes/ from the sample app in examples/taskboard
npm run example:draft      # silent draft + contact sheet in out/
npm run example:build      # the real thing, with voice and GIF
```

### A recording script

```js
import { chromium } from 'playwright';
import { Director } from './skills/democut/kit/director.mjs';

const browser = await chromium.launch();
const d = await Director.open(browser, 'app', '.takes');
await d.goto('http://localhost:3000');
await d.scene('add-task', async () => {
  await d.click('#add');
  await d.type('#title', 'Record the launch demo');
  await d.click('#save');
  await d.zoom('.card >> nth=0');
  await d.hold(1200);
});
await d.close();
await browser.close();
```

Full API: [`references/director.md`](skills/democut/references/director.md) ·
storyboard schema: [`references/storyboard.md`](skills/democut/references/storyboard.md) ·
writing tips: [`references/storytelling.md`](skills/democut/references/storytelling.md)

## Why not ...

- **Remotion** is great, but needs a paid company licence above three people, and rebuilding your UI in React is
  a different job from recording the real thing. democut is MIT end to end.
- **Screen Studio / Loom** are manual. democut is re-runnable: when the UI changes, re-record and rebuild.
- **Cloud TTS** means accounts, keys and sending your script out. Kokoro runs offline on a laptop CPU.

## Voices and licences

democut's code is MIT. The default voice is [Kokoro-82M](https://github.com/hexgrad/kokoro) (Apache-2.0
weights), run through [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx). Bring any other engine with a
one-line `command`. Read [`references/voices.md`](skills/democut/references/voices.md) before you pick a voice:
some popular open voices are trained on research-only data. Third-party notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Contributing

Issues and PRs are welcome: new example apps, more voices, transitions, a vertical cut for social video.
See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

[MIT](LICENSE) © Javad Farshchi
