#!/usr/bin/env python3
"""Start a new democut project, or check that everything democut needs is installed.

  python init.py doctor                       # check node, playwright, ffmpeg, python packages, voice
  python init.py new DIR --url URL [--name N] # write DIR/record.mjs and DIR/storyboard.json to edit

MIT licence.
"""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys

KIT = os.path.dirname(os.path.abspath(__file__))


def doctor():
    ok = True

    def row(good, name, hint=''):
        nonlocal ok
        ok = ok and good
        print(f'  {"ok " if good else "MISSING"}  {name}' + ('' if good else f'\n           -> {hint}'))

    print('democut doctor')
    row(sys.version_info >= (3, 9), f'python {sys.version.split()[0]} (3.9+)', 'install Python 3.9 or newer')
    node = shutil.which('node')
    row(bool(node), 'node', 'install Node.js 18+')
    if node:
        pw = subprocess.run([node, '-e', "require.resolve('playwright')"], capture_output=True).returncode == 0
        row(pw, 'playwright (resolvable from this folder)', 'npm i -D playwright && npx playwright install chromium')
    row(bool(shutil.which('ffmpeg')), 'ffmpeg', 'brew install ffmpeg  |  apt install ffmpeg  |  winget install ffmpeg')
    for mod, pkg in (('numpy', 'numpy'), ('cv2', 'opencv-python-headless'), ('PIL', 'pillow')):
        row(importlib.util.find_spec(mod) is not None, pkg, f'pip install {pkg}')
    has_k = importlib.util.find_spec('kokoro_onnx') is not None and importlib.util.find_spec('soundfile') is not None
    row(has_k, 'kokoro-onnx + soundfile (voice; optional with --tts none)', 'pip install kokoro-onnx soundfile')
    base = os.environ.get('DEMOCUT_KOKORO_DIR', os.path.join(os.path.expanduser('~'), '.cache', 'democut', 'kokoro'))
    files = all(os.path.exists(os.path.join(base, f)) for f in ('kokoro-v1.0.int8.onnx', 'voices-v1.0.bin'))
    row(files, f'Kokoro voice files in {base}', f'bash {os.path.join(KIT, "get-voice.sh")}')
    print('all good' if ok else 'fix the MISSING lines above (the voice is optional: build with --tts none)')
    return 0 if ok else 1


RECORD = r"""// Recording script for {name}. Run: node {rel}/record.mjs
// Each d.scene(...) becomes one shot. Navigation and loading go outside scenes, so they are cut.
import {{ chromium }} from 'playwright';
import {{ Director }} from '{director}';

const APP_URL = process.env.DEMO_URL || '{url}';
const OUT = new URL('./.takes', import.meta.url).pathname;

const browser = await chromium.launch();
const d = await Director.open(browser, 'app', OUT, {{
  // mask: [['acct_[A-Za-z0-9]+', 'g', 'acct_••••']],   // emails are masked by default
  // hide: ['#cookie-banner'],
}});

await d.goto(APP_URL);

await d.scene('overview', async () => {{
  await d.hold(800);
  await d.hover('h1, header, nav');                   // TODO: something the viewer should notice first
  await d.hold(1200);
}});

await d.scene('main-action', async () => {{
  // TODO: the one thing your product does best. For example:
  // await d.click('text=New project');
  // await d.type('input[name=name]', 'Launch plan');
  // await d.click('text=Create');
  // await d.zoom('.result', {{ fill: 0.6 }});
  await d.hold(1500);
}});

await d.close();
await browser.close();
"""


def storyboard(name):
    return {
        'title': f'{name} demo',
        'description': f'A short tour of {name}.',
        'voice': {'engine': 'kokoro', 'voice': 'af_heart', 'speed': 1.0, 'lang': 'en-us'},
        'theme': {'background': ['#0f172a', '#312e81'], 'accent': '#a5b4fc', 'window_title': name},
        'takes': {'app': {'badge': 'LIVE', 'note': 'real app', 'color': '#22c55e'}},
        'cuts': {'full': '*', 'short': ['intro', 'main-action', 'outro']},
        'cut_labels': {'full': 'Full demo', 'short': 'Short cut'},
        'shots': [
            {'id': 'intro', 'card': {'kicker': name.upper(), 'title': 'TODO: the problem, in one line',
                                     'sub': 'TODO: three things you will see'},
             'say': f'TODO: who is stuck, and on what. Then: here is how {name} fixes it.'},
            {'id': 'overview', 'take': 'app', 'scene': 'overview', 'chapter': 'Overview',
             'say': 'TODO: what the viewer is looking at, and why it matters.'},
            {'id': 'main-action', 'take': 'app', 'scene': 'main-action', 'chapter': 'Overview',
             'say': 'TODO: what this click buys the user, not what the click is.'},
            {'id': 'outro', 'card': {'kicker': 'TRY IT', 'title': 'TODO: your URL or install command',
                                     'chapter_title': 'Get started'},
             'say': 'TODO: one call to action.'},
        ],
    }


def new(args):
    os.makedirs(args.dir, exist_ok=True)
    name = args.name or os.path.basename(os.path.abspath(args.dir)).replace('-', ' ').title()
    rec, sb = os.path.join(args.dir, 'record.mjs'), os.path.join(args.dir, 'storyboard.json')
    for p in (rec, sb):
        if os.path.exists(p) and not args.force:
            sys.exit(f'{p} exists (use --force to overwrite)')
    director = os.path.relpath(os.path.join(KIT, 'director.mjs'), os.path.abspath(args.dir)).replace(os.sep, '/')
    if not director.startswith('.'):
        director = './' + director
    open(rec, 'w').write(RECORD.format(name=name, url=args.url, director=director, rel=args.dir))
    json.dump(storyboard(name), open(sb, 'w'), indent=2)
    build = os.path.join(KIT, 'build.py')
    print(f"""wrote {rec} and {sb}

next:
  1. edit the TODOs (scenes in record.mjs, narration in storyboard.json)
  2. node {rec}
  3. python {build} {sb} --takes {args.dir}/.takes --out {args.dir}/out --tts none --preset ultrafast --sheet   # draft
  4. python {build} {sb} --takes {args.dir}/.takes --out {args.dir}/out --gif short                           # final""")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('doctor')
    n = sub.add_parser('new')
    n.add_argument('dir')
    n.add_argument('--url', required=True)
    n.add_argument('--name')
    n.add_argument('--force', action='store_true')
    args = ap.parse_args()
    sys.exit(doctor() if args.cmd == 'doctor' else new(args))


if __name__ == '__main__':
    main()
