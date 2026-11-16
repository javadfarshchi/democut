# Changelog

## 0.2.0 (2026-11-16)

- `init.py doctor`: checks Node, Playwright, ffmpeg, Python packages and the voice, and prints the fix for each.
- `init.py new DIR --url URL`: writes a recording script and storyboard with TODOs to fill in.
- Captions no longer overlap when one caption hands over to the next.
- Per-take `window_title` in the storyboard.
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
