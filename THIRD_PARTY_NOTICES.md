# Third-party notices

democut's own code is MIT (see LICENSE). It ships one third-party asset and uses other software you install
yourself.

## Shipped in this repository

| Asset | Where | Licence |
|---|---|---|
| Inter typeface (Regular, Medium, SemiBold, Bold) by The Inter Project Authors | `skills/democut/kit/fonts/` | SIL Open Font License 1.1, full text in `skills/democut/kit/fonts/OFL.txt` |

## Installed by you, not shipped

| Software | Used for | Licence |
|---|---|---|
| Playwright | browser recording | Apache-2.0 |
| ffmpeg | decoding, encoding, GIF | LGPL-2.1+ or GPL-2.0+, depending on your build; called as an external program |
| NumPy, Pillow, opencv-python-headless | frame processing | BSD-3-Clause, MIT-CMU (HPND), Apache-2.0 |
| kokoro-onnx (optional) | running the voice | MIT |
| Kokoro-82M weights and voices (optional, downloaded by `get-voice.sh`) | the default voice | Apache-2.0 |
| phonemizer, espeak-ng (pulled in by kokoro-onnx) | turning text into phonemes | GPL-3.0 |
| onnxruntime, soundfile | running the model, writing audio | MIT, BSD-3-Clause |

## Inspiration

Techniques such as the eased cursor, click ripple, hold-before-click and idle speed-up are widely used in demo
tools, including playwright-recast (MIT) and Screenwright (MIT). democut implements them independently; no code
from those projects is included.
