# Contributing

Thanks for helping. Small, focused PRs are easiest to review.

- **Run the example end to end** before opening a PR that touches the kit:
  `npm run example:record && npm run example:draft`, then look at `out/contact-sheet.png`.
- **Keep the kit dependency-light.** Python: numpy, opencv, pillow. Node: playwright. New runtime dependencies
  need a good reason and an MIT-compatible licence.
- **No secrets or private data** in examples, recordings or screenshots. Use made-up names and `example.com`.
- **Voices:** only add a voice or engine whose licence allows commercial use, and document it in
  `skills/democut/references/voices.md`.

Ideas that would help: a vertical 9:16 cut, background music with ducking, more example apps, a Windows check,
better caption timing from word-level timestamps.
