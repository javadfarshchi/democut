---
name: democut
description: Make a narrated, captioned product demo video of a web app. Records the real app with Playwright (eased cursor, click ripples, zooms, typing), voices it offline with Kokoro, and edits it into a full cut, a short cut, SRT/VTT captions, chapters, a README GIF and a player page. Use when asked for a demo video, product walkthrough, screencast, feature tour, launch video or README GIF of a web app.
license: MIT
---

# democut: narrated product demos, written as code

You turn a web app into a demo video a person would be proud to share. You write the story, record the real app in
a browser, and let democut's editor do the cutting, zooming, captions, voice and packaging.

`KIT` below means the `kit/` folder next to this SKILL.md. Use its absolute path in commands.

## Outputs (per cut, in the output folder)

`<cut>.mp4` (1080p, chapters embedded) · `<cut>.srt` · `<cut>.vtt` · `<cut>.chapters.txt` · `<cut>.transcript.json` ·
`poster.png` · `index.html` (player with chapters, captions, clickable transcript) · optional `<cut>.gif` and
`contact-sheet.png`.

## Workflow

### 1. Check the tools (once)

```bash
python KIT/init.py doctor                       # lists anything missing, with the command to fix it
```

Typical fixes: `npm i -D playwright && npx playwright install chromium`, ffmpeg from the OS package manager,
`pip install numpy opencv-python-headless pillow kokoro-onnx soundfile`, and `bash KIT/get-voice.sh` for the
Kokoro voice (~120 MB, once).

To start a new demo folder with a recording script and storyboard to fill in:
`python KIT/init.py new demos/<name> --url <app url>`.

If the person cannot install the voice, use `--tts none` (silent, captions only) or a `command` engine
(see `references/voices.md`). Never use a voice whose licence you have not checked.

### 2. Write the story before touching code

Read `references/storytelling.md`. In short: open with the viewer's problem, not the product. Pick one persona,
3 to 5 chapters, one idea per shot, and spoken narration of at most ~25 words per shot. Plan a full cut
(2 to 3 minutes) and a short cut (30 to 60 seconds) from the same shots.

Show the plan to the person (chapters, shot list, narration) before recording if they are around; otherwise proceed.

### 3. Decide the takes and be honest about them

A take is one recorded browser session. Give each take a badge that says where its pixels come from, for example
`LIVE` (real app), `STAGING`, `STUBBED` (real UI, test data), `SAMPLE DATA`, `TERMINAL`. Never present test data
as live.

### 4. Write the recording script

Start from `references/director.md`. A complete working example (sample app, recording script, storyboard) is in
`examples/taskboard/` at the plugin root, three folders up from `KIT`. Rules:

- One `Director.open(browser, '<take>', outDir, opts)` per take; `await d.close()` at the end.
- Wrap every moment worth showing in `await d.scene('<id>', async () => { ... })`. Time outside scenes is cut,
  so navigate (`d.goto`) and wait for data **outside** scenes.
- Use `d.click`, `d.type`, `d.hover`, `d.scroll`, `d.zoom(target)`; avoid raw `page.click` inside scenes, because
  viewers cannot follow a click without the cursor.
- Hold on results (`d.hold(800..1500)`) so the narration has room. The editor speeds long scenes up (max 1.7x)
  and holds the last frame of short ones.
- Privacy: emails are masked by default. Add patterns for anything else private (`mask`), hide dev toolbars and
  cookie banners (`hide`). Sign in with a separate, unrecorded context and pass `storageState`. Never type real
  passwords inside a recorded take.
- Only read-only actions against shared or production systems unless the person explicitly allows writes.

Run it, then check every scene id appears in `<take>.timeline.json`.

### 5. Write the storyboard

`storyboard.json` lists shots in order: chapter cards and recorded scenes, each with its narration (`say`).
Full schema with an example: `references/storyboard.md`.

### 6. Draft, look, fix

```bash
python KIT/build.py storyboard.json --takes TAKES --out OUT --tts none --preset ultrafast --sheet
```

Open `OUT/contact-sheet.png` (one frame per shot) and look at it. Check: is each zoom on the right element, is
anything private visible, is any shot blank or mid-load, do captions cover something important? Fix the recording
or storyboard and redraft. This loop is cheap; do it at least once.

### 7. Final build

```bash
python KIT/build.py storyboard.json --takes TAKES --out OUT --gif short --gif-range 0-14 --sheet
```

Kokoro takes about 1 to 3 s per sentence on a laptop CPU; audio is cached, so rebuilds are fast.

### 8. Deliver

Give the person the player page (`OUT/index.html`, serve the folder or open it directly), the MP4s, and the GIF.
Say which shots are not live and any caveat (for example a known bug visible on screen).

## Troubleshooting

- `scene "x" not in ...`: the scene id in the storyboard does not match the recording script.
- Zoom lands on the wrong place: the target moved after `zoom()`; zoom after the UI settles, and do not scroll while
  zoomed.
- Blurry text: keep the viewport at 1440x810 (default). Playwright video ignores `deviceScaleFactor`, so a larger
  zoom than ~1.6x gets soft.
- Narration too fast or slow: change `voice.speed` (0.9 to 1.1) or shorten the sentence.
