# Changelog

## 0.3.0 (2026-11-17)

- Vibrant backgrounds: seven mesh-gradient presets (`aurora`, `sunset`, `ocean`, `candy`, `citrus`, `ember`,
  `midnight`) with slowly drifting colour, film grain against banding and a soft vignette. Custom colours or a
  brand image work too. Set `theme.background`; the default is `aurora`.
- A soft halo behind card text and darker badge pills, so text stays readable on bright colours.
- About 4x faster frame compositing.

## 0.2.0 (2026-11-16)

- `init.py doctor`: checks Node, Playwright, ffmpeg, Python packages and the voice, and prints the fix for each.
- `init.py new DIR --url URL`: writes a recording script and storyboard with TODOs to fill in.
- README rewritten: quickstart first, prompts to try, feature GIFs, what leaves your computer.

## 0.1.0 (2026-11-16)

First release.

- Director (Playwright): eased cursor, click ripples, human-paced typing, scene marks, zoom marks, DOM masking.
- Editor: per-shot timing to narration, eased zooms, speed-up and hold, framed window, badges, chapter cards,
  burned-in captions, crossfades, MP4 chapters, SRT/VTT, transcript JSON, poster, GIF, contact sheet.
- Player page with cut switcher, chapters and transcript.
- Offline Kokoro voice; `none` and `command` engines.
- Terminal replay page for CLI shots.
- Claude Code plugin + marketplace; SKILL.md works with other agents.
- Example: Taskboard sample app and the self-demo storyboard.
