# Voices and licences

| Engine | Setup | Licence notes |
|---|---|---|
| `kokoro` (default) | `pip install kokoro-onnx soundfile` and `bash kit/get-voice.sh` | Kokoro-82M weights and voices are Apache-2.0, fine for commercial use. Runs offline on CPU. The `kokoro-onnx` package pulls in `phonemizer` and an espeak-ng library, which are GPL-3.0; they are installed by you at run time and are not part of democut, and they do not affect the licence of the audio you make. |
| `none` | nothing | Silent video with captions; shot length comes from word count. Good for drafts. |
| `command` | any CLI that reads text on stdin and writes WAV to `{out}` | Your responsibility. Examples below. |

```json
{ "voice": { "engine": "command", "command": "piper -m en_US-amy-medium.onnx -f {out}" } }
{ "voice": { "engine": "command", "command": "say -o {out} --data-format=LEI16@24000" } }
```

Check the voice's own licence before publishing. Some popular open voices are trained on research-only datasets
(for example several Piper voices trained on the Blizzard 2013 "Lessac" data). Each Piper voice has a MODEL_CARD
with its dataset licence. Cloud voices are fine when you have an account whose terms allow your use; avoid
unofficial endpoints for commercial videos.

Good Kokoro voices for English demos: `af_heart`, `af_bella`, `am_michael`, `am_fenrir`, `bf_emma`, `bm_george`.
