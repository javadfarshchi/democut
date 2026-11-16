# storyboard.json

```json
{
  "title": "Acme in 90 seconds",
  "description": "Shown on the player page.",
  "voice": { "engine": "kokoro", "voice": "af_heart", "speed": 1.0, "lang": "en-us" },
  "theme": { "background": ["#0f172a", "#312e81"], "accent": "#a5b4fc", "window_title": "app.acme.test" },
  "takes": {
    "live":    { "badge": "LIVE",    "note": "staging, read-only", "color": "#22c55e" },
    "stubbed": { "badge": "STUBBED", "note": "real UI, test data", "color": "#f59e0b", "window_title": "localhost" }
  },
  "cuts": { "full": "*", "short": ["intro", "add", "outro"] },
  "cut_labels": { "full": "Full demo", "short": "60-second cut" },
  "shots": [
    { "id": "intro", "card": { "kicker": "ACME", "title": "Ship invoices in one click", "sub": "Import · Review · Send" },
      "say": "Every month, Dana spends a day on invoices. Here is how Acme makes it one click.",
      "say_short": "Here is how Acme makes invoicing one click." },
    { "id": "add", "take": "live", "scene": "add-invoice", "chapter": "1 · Import",
      "say": "She drops in last month's timesheet, and Acme drafts every invoice." },
    { "id": "ch2", "card": { "kicker": "CHAPTER 2", "title": "Review" }, "say": "Next, review." },
    { "id": "review", "take": "stubbed", "scene": "review", "note": "Known issue: totals column is cut off on small screens",
      "say": "Anything unusual is flagged before it goes out." },
    { "id": "outro", "card": { "kicker": "TRY IT", "title": "acme.test", "chapter_title": "Get started" },
      "say": "Try it free at acme dot test." }
  ]
}
```

## Fields

| Field | Meaning |
|---|---|
| `title`, `description` | Player page title and blurb; `title` is also the MP4 title. |
| `voice.engine` | `kokoro` (default, offline), `none` (silent; shot length from word count), `command`. |
| `voice.voice`, `speed`, `lang` | Kokoro voice id (`af_heart`, `am_michael`, `bf_emma`, ...), speed 0.5 to 2.0, language. |
| `voice.command` | For `command`: a shell command that reads text on stdin and writes a WAV to `{out}`. |
| `theme.background` | Two hex colours for the backdrop gradient. `accent` colours card kickers. |
| `theme.window_title` | Text in the window chrome around recordings. A take can override it. |
| `takes.<name>` | Badge per take: `badge`, `note`, `color`, optional `window_title`. The name matches `Director.open(browser, name, ...)`. |
| `cuts` | Named cuts. `"*"` means every shot in order; a list picks shots by id, in that order. Default `{"full": "*"}`. |
| `cut_labels` | Button labels on the player page. |
| `shots[].id` | Unique id, used by `cuts` and in the contact sheet. |
| `shots[].card` | A full-screen title card: `kicker`, `title`, `sub`. Cards start chapters unless `"chapter": false`; `chapter_title` overrides the chapter name. |
| `shots[].take`, `scene` | A recorded scene: the take name and the `d.scene(id)` inside it. |
| `shots[].chapter` | Label shown top right on the shot (defaults to the current chapter). |
| `shots[].say` | Narration. Also becomes the burned-in captions, SRT/VTT and transcript. |
| `shots[].say_<cut>` | Narration override for one cut, e.g. `say_short`. |
| `shots[].note` | A yellow banner above the captions, for caveats such as a known bug on screen. |

## Timing rules

A recorded shot lasts `max(narration + 1.2 s, scene length / max_speed)`. If the scene is longer than that, it is
sped up (at most `--max-speed`, default 1.7); if shorter, its last frame is held. A card lasts narration + 1.45 s.
Shots crossfade for 0.35 s.
