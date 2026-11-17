#!/usr/bin/env python3
"""democut editor: turn recorded takes + a storyboard into narrated, captioned demo videos.

  python build.py STORYBOARD.json --takes DIR --out DIR [--cut NAME ...] [--gif CUT] [--sheet] [--tts ENGINE]

For every shot in a cut it:
  * cuts the scene out of its take (page loads between scenes are dropped),
  * applies the zooms the director marked (eased, sub-pixel),
  * speeds a long clip up (at most --max-speed) or holds its last frame so it fits the narration,
  * frames the app in a window on a backdrop, burns in the take's badge, the chapter and captions,
  * renders chapter cards, crossfades between shots, and mixes the voiceover.

Writes per cut: CUT.mp4 (with chapters), CUT.srt, CUT.vtt, CUT.chapters.txt, CUT.transcript.json, plus
poster.png, index.html (a player with chapters, captions and transcript) and optionally CUT.gif / contact-sheet.png.

Needs ffmpeg on PATH and: pip install numpy opencv-python-headless pillow  (+ kokoro-onnx soundfile for the voice).
MIT licence.
"""
import argparse
import hashlib
import html
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import wave

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

KIT = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1920, 1080, 30, 24000
LEAD, TAIL, XFADE = 0.45, 0.75, 0.35


def font(weight, size):
    name = {'r': 'Inter-Regular.otf', 'm': 'Inter-Medium.otf', 's': 'Inter-SemiBold.otf', 'b': 'Inter-Bold.otf'}[weight]
    return ImageFont.truetype(os.path.join(KIT, 'fonts', name), size)


def hex_rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def log(*a):
    print('[democut]', *a, flush=True)


# ---------------------------------------------------------------- voice

class Voice:
    """Text to mono float32 audio at SR. Engines: kokoro (offline, Apache-2.0 weights), none (silent), command."""

    def __init__(self, cfg, engine_override, cache):
        self.cfg = dict(cfg or {})
        self.engine = engine_override or self.cfg.get('engine', 'kokoro')
        self.cache = cache
        self._kokoro = None
        os.makedirs(cache, exist_ok=True)

    def _key(self, text):
        h = hashlib.sha1(json.dumps([self.engine, self.cfg, text], sort_keys=True).encode()).hexdigest()[:16]
        return os.path.join(self.cache, h + '.wav')

    def say(self, text):
        if self.engine == 'none':
            words = max(1, len(text.split()))
            return np.zeros(int(SR * (words / 2.6 + 0.3)), np.float32)
        out = self._key(text)
        if not os.path.exists(out):
            if self.engine == 'kokoro':
                self._kokoro_say(text, out)
            elif self.engine == 'command':
                cmd = self.cfg.get('command')
                if not cmd:
                    sys.exit('voice.engine "command" needs voice.command, e.g. "piper -m my.onnx -f {out}"')
                subprocess.run(shlex.split(cmd.replace('{out}', shlex.quote(out))), input=text.encode(), check=True,
                               stdout=subprocess.DEVNULL)
            else:
                sys.exit(f'unknown voice engine {self.engine!r} (kokoro | none | command)')
        return read_wav(out)

    def _kokoro_say(self, text, out):
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro
            except ImportError:
                sys.exit('The kokoro voice needs: pip install kokoro-onnx soundfile   (or use --tts none)')
            model, voices = kokoro_files(self.cfg)
            self._kokoro = Kokoro(model, voices)
        import soundfile as sf
        samples, sr = self._kokoro.create(text, voice=self.cfg.get('voice', 'af_heart'),
                                          speed=float(self.cfg.get('speed', 1.0)), lang=self.cfg.get('lang', 'en-us'))
        sf.write(out, samples, sr)


def kokoro_files(cfg):
    base = os.environ.get('DEMOCUT_KOKORO_DIR', os.path.join(os.path.expanduser('~'), '.cache', 'democut', 'kokoro'))
    model = cfg.get('model') or os.path.join(base, 'kokoro-v1.0.int8.onnx')
    voices = cfg.get('voices') or os.path.join(base, 'voices-v1.0.bin')
    if not (os.path.exists(model) and os.path.exists(voices)):
        sys.exit(f'Kokoro model files missing in {base}. Run: bash {os.path.join(KIT, "get-voice.sh")}')
    return model, voices


def read_wav(path):
    with wave.open(path) as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if sw == 2:
        a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    elif sw == 4:
        a = np.frombuffer(raw, np.int32).astype(np.float32) / 2147483648
    else:
        a = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if sr != SR and len(a):
        a = np.interp(np.linspace(0, len(a) - 1, int(len(a) * SR / sr)), np.arange(len(a)), a).astype(np.float32)
    return a


# ---------------------------------------------------------------- drawing

def wrap(d, text, f, width):
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if cur and d.textlength(t, font=f) > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


class Layer:
    """RGBA overlay cropped to its bounding box and premultiplied, for fast blending onto BGR frames."""

    def __init__(self, im):
        bb = im.getbbox() or (0, 0, 1, 1)
        self.x0, self.y0, self.x1, self.y1 = bb
        a = np.array(im)[self.y0:self.y1, self.x0:self.x1].astype(np.float32)
        self.alpha = a[..., 3:4] / 255.0
        self.rgb = a[..., [2, 1, 0]] * self.alpha

    def blend(self, frame, opacity=1.0, dy=0):
        if opacity <= 0:
            return
        y0, y1 = self.y0 + dy, self.y1 + dy
        if y1 > frame.shape[0]:
            return
        r = frame[y0:y1, self.x0:self.x1].astype(np.float32)
        frame[y0:y1, self.x0:self.x1] = (r * (1 - self.alpha * opacity) + self.rgb * opacity).astype(np.uint8)


def blank():
    return Image.new('RGBA', (W, H), (0, 0, 0, 0))


# Background presets: a deep base colour with soft, slowly drifting colour blobs (a "mesh gradient"),
# a little film grain against banding, and a gentle vignette.
PRESETS = {
    'aurora':   ('#0b1026', ['#7c3aed', '#06b6d4', '#22c55e', '#ec4899']),
    'sunset':   ('#1a0b2e', ['#f97316', '#ec4899', '#8b5cf6', '#facc15']),
    'ocean':    ('#031b34', ['#0ea5e9', '#22d3ee', '#6366f1', '#14b8a6']),
    'candy':    ('#2a0a3d', ['#f472b6', '#a78bfa', '#60a5fa', '#fb7185']),
    'citrus':   ('#0f2a1d', ['#a3e635', '#facc15', '#22c55e', '#f97316']),
    'ember':    ('#1c0a00', ['#ef4444', '#f97316', '#f59e0b', '#be123c']),
    'midnight': ('#020617', ['#1d4ed8', '#7c3aed', '#0891b2']),
}
BG_SCALE = 4  # the blob field is computed at 1/4 size; it is smooth, so upscaling loses nothing


class Backdrop:
    """theme.background: a preset name, {"preset"|"colors"+"base", "motion", "grain"}, two hex colours (a linear
    gradient), or {"image": "path.png"}."""

    def __init__(self, spec, story_dir):
        self.static = None
        if isinstance(spec, list):
            c0, c1 = (np.array(hex_rgb(c)[::-1], np.float32) for c in spec[:2])
            yy, xx = np.mgrid[0:H, 0:W]
            g = (xx / W * 0.6 + yy / H * 0.4)[..., None]
            self.static = (c0 * (1 - g) + c1 * g).astype(np.uint8)
            return
        if isinstance(spec, str):
            spec = {'preset': spec}
        spec = spec or {'preset': 'aurora'}
        if 'image' in spec:
            path = spec['image'] if os.path.isabs(spec['image']) else os.path.join(story_dir, spec['image'])
            img = cv2.imread(path)
            if img is None:
                sys.exit(f'background image not found: {path}')
            h, w = img.shape[:2]
            k = max(W / w, H / h)
            img = cv2.resize(img, (int(w * k + 1), int(h * k + 1)), interpolation=cv2.INTER_AREA)
            y, x = (img.shape[0] - H) // 2, (img.shape[1] - W) // 2
            self.static = img[y:y + H, x:x + W].copy()
            return
        name = spec.get('preset', 'aurora')
        if 'colors' in spec:
            base, colors = spec.get('base', '#0b1026'), spec['colors']
        elif name in PRESETS:
            base, colors = PRESETS[name]
        else:
            sys.exit(f'unknown background preset {name!r}; choose from: {", ".join(PRESETS)}')
        self.base = np.array(hex_rgb(base)[::-1], np.float32) / 255
        self.colors = [np.array(hex_rgb(c)[::-1], np.float32) / 255 for c in colors]
        self.motion = bool(spec.get('motion', True))
        rng = np.random.default_rng(7)
        self.paths = [(rng.uniform(0, 6.28), rng.uniform(0, 6.28), rng.uniform(0.035, 0.06), rng.uniform(0.03, 0.05))
                      for _ in self.colors]
        h, w = H // BG_SCALE, W // BG_SCALE
        self.yy, self.xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.yy /= h
        self.xx /= w
        r2 = (self.xx - 0.5) ** 2 + (self.yy - 0.5) ** 2
        self.vignette = (1 - 0.22 * r2)[..., None]
        self.grain = None
        if spec.get('grain', True):  # fine noise against banding in smooth gradients, as add/subtract planes
            g = np.clip(rng.normal(0, 1.6, (H, W, 1)), -6, 6).repeat(3, 2)
            self.grain = (np.clip(g, 0, None).astype(np.uint8), np.clip(-g, 0, None).astype(np.uint8))
        self._still = None

    def at(self, t=0.0):
        if self.static is not None:
            return self.static
        if not self.motion:
            if self._still is None:
                self._still = self._render(0.0)
            return self._still
        return self._render(t)

    def _render(self, t):
        rgb = np.empty(self.xx.shape + (3,), np.float32)
        rgb[:] = self.base
        n = len(self.colors)
        for i, (c, (p1, p2, w1, w2)) in enumerate(zip(self.colors, self.paths)):
            # each blob drifts on its own slow loop around a home position spread across the frame
            hx = (i + 0.5) / n
            hy = 0.18 if i % 2 == 0 else 0.82  # alternate top and bottom, where the frame shows around the window
            cx = hx + 0.18 * np.sin(t * w1 * 6.28 / 3 + p1)
            cy = hy + 0.14 * np.cos(t * w2 * 6.28 / 3 + p2)
            r = 0.34 + 0.06 * np.sin(t * 0.07 + p1)
            wgt = 0.92 * np.exp(-(((self.xx - cx) * 1.78) ** 2 + (self.yy - cy) ** 2) / (2 * r * r))
            rgb = rgb * (1 - wgt[..., None]) + c * wgt[..., None]
        small = np.clip(rgb * self.vignette * 255 + 0.5, 0, 255).astype(np.uint8)
        big = cv2.resize(small, (W, H), interpolation=cv2.INTER_CUBIC)
        if self.grain is not None:
            big = cv2.subtract(cv2.add(big, self.grain[0]), self.grain[1])
        return big


class Look:
    def __init__(self, theme, story_dir='.'):
        theme = theme or {}
        self.bg = Backdrop(theme.get('background', 'aurora'), story_dir)
        self.accent = hex_rgb(theme.get('accent', '#e0e7ff'))
        self.window_title = theme.get('window_title', '')
        self._frames = {}

    def backdrop(self, t=0.0):
        return self.bg.at(t)

    def frame_kit(self, title=None):
        """Window chrome (as an overlay layer), drop-shadow multiplier, and where the app goes."""
        title = self.window_title if title is None else title
        if title in self._frames:
            return self._frames[title]
        bar = 34
        fw, fh = int(W * 0.8), int(H * 0.8)
        x0, y0 = (W - fw) // 2, 86
        sh = np.zeros((H, W), np.float32)
        cv2.rectangle(sh, (x0, y0 + 22), (x0 + fw, y0 + bar + fh + 22), 1.0, -1)
        sh = 1 - cv2.GaussianBlur(sh, (0, 0), 34) * 0.55
        sy0, sy1 = max(0, y0 - 120), min(H, y0 + bar + fh + 140)
        sh = np.clip(sh[sy0:sy1] * 255 + 0.5, 0, 255).astype(np.uint8)[..., None].repeat(3, 2)
        chrome = blank()
        d = ImageDraw.Draw(chrome)
        d.rounded_rectangle((x0 - 1, y0 - 1, x0 + fw + 1, y0 + bar + fh + 1), 17, fill=(255, 255, 255, 60))
        d.rounded_rectangle((x0, y0, x0 + fw, y0 + bar + fh), 16, fill=(30, 33, 40, 255))
        for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
            d.ellipse((x0 + 16 + i * 20, y0 + 11, x0 + 28 + i * 20, y0 + 23), fill=c + (255,))
        if title:
            f = font('m', 16)
            d.text((x0 + (fw - d.textlength(title, font=f)) / 2, y0 + 8), title, font=f, fill=(170, 175, 185, 255))
        mask = np.zeros((fh, fw), np.uint8)
        r = 14
        cv2.rectangle(mask, (0, 0), (fw, fh - r), 255, -1)
        cv2.rectangle(mask, (r, 0), (fw - r, fh), 255, -1)
        for cx in (r, fw - r - 1):
            cv2.circle(mask, (cx, fh - r - 1), r, 255, -1, cv2.LINE_AA)
        # only the parts of the chrome the app does not cover: title bar, side edges, bottom edge and corners
        parts = [(0, 0, W, y0 + bar + 1), (0, y0 + bar, x0 + 1, H), (x0 + fw - 1, y0 + bar, W, H),
                 (0, y0 + bar + fh - r - 2, W, H)]
        layers = []
        for box in parts:
            piece = blank()
            piece.paste(chrome.crop(box), box[:2])
            layers.append(Layer(piece))
        corner = (mask[fh - r - 2:, :].astype(np.float32) / 255)[..., None]
        self._frames[title] = (layers, (sy0, sy1, sh), (x0, y0 + bar, fw, fh), corner)
        return self._frames[title]

    def framed(self, img, title=None, t=0.0):
        layers, (sy0, sy1, shadow), (x0, y0, fw, fh), corner = self.frame_kit(title)
        out = self.backdrop(t).copy()
        out[sy0:sy1] = cv2.multiply(out[sy0:sy1], shadow, scale=1 / 255)
        for lay in layers:
            lay.blend(out)
        small = cv2.resize(img, (fw, fh), interpolation=cv2.INTER_AREA)
        k = corner.shape[0]
        reg = out[y0 + fh - k:y0 + fh, x0:x0 + fw].astype(np.float32)
        bottom = (small[fh - k:].astype(np.float32) * corner + reg * (1 - corner)).astype(np.uint8)
        out[y0:y0 + fh, x0:x0 + fw] = small
        out[y0 + fh - k:y0 + fh, x0:x0 + fw] = bottom
        return out

    def badge(self, take, chapter):
        im = blank()
        d = ImageDraw.Draw(im)
        y = 22
        if take and take.get('badge'):
            tag, desc = take['badge'], take.get('note', '')
            col = hex_rgb(take.get('color', '#16a34a'))
            f1, f2 = font('b', 22), font('m', 22)
            tw = d.textlength(tag, font=f1)
            dw = d.textlength(desc, font=f2) if desc else -12
            x = 192
            d.rounded_rectangle((x, y, x + tw + dw + 56, y + 44), 22, fill=(10, 14, 28, 140))
            d.ellipse((x + 16, y + 16, x + 28, y + 28), fill=col + (255,))
            d.text((x + 38, y + 9), tag, font=f1, fill=(255, 255, 255, 255))
            if desc:
                d.text((x + 38 + tw + 12, y + 9), desc, font=f2, fill=(203, 213, 225, 255))
        if chapter:
            f2 = font('m', 22)
            cw = d.textlength(chapter, font=f2)
            d.rounded_rectangle((W - 192 - cw - 36, y, W - 192, y + 44), 22, fill=(10, 14, 28, 140))
            d.text((W - 192 - cw - 18, y + 9), chapter, font=f2, fill=(255, 255, 255, 255))
        return Layer(im)

    def caption(self, text, note=None):
        im = blank()
        d = ImageDraw.Draw(im)
        f = font('m', 36)
        lines = wrap(d, text, f, W * 0.8)
        lh = 52
        bw = max(d.textlength(l, font=f) for l in lines) + 64
        bh = lh * len(lines) + 30
        x0, y0 = (W - bw) / 2, H - 28 - bh
        d.rounded_rectangle((x0, y0, x0 + bw, y0 + bh), 18, fill=(10, 14, 28, 210))
        for i, l in enumerate(lines):
            d.text(((W - d.textlength(l, font=f)) / 2, y0 + 15 + i * lh), l, font=f, fill=(255, 255, 255, 255))
        if note:
            fn = font('m', 24)
            nw = d.textlength(note, font=fn) + 40
            d.rounded_rectangle(((W - nw) / 2, y0 - 58, (W + nw) / 2, y0 - 16), 12, fill=(254, 243, 199, 240))
            d.text(((W - nw) / 2 + 20, y0 - 50), note, font=fn, fill=(120, 53, 15, 255))
        return Layer(im)

    def card(self, card):
        im = blank()
        d = ImageDraw.Draw(im)
        fk, ft, fs = font('s', 26), font('b', 84), font('m', 32)
        tl = wrap(d, card.get('title', ''), ft, W - 300)
        sl = wrap(d, card.get('sub', ''), fs, W - 300) if card.get('sub') else []
        y = H / 2 - 60 - (len(tl) - 1) * 50

        def draw(d, shadow):
            white, soft = ((0, 0, 0, 255),) * 2 if shadow else ((255, 255, 255, 255), (235, 240, 250, 255))
            acc = (0, 0, 0, 255) if shadow else self.accent + (255,)
            if card.get('kicker'):
                d.rounded_rectangle((150, y - 92, 230, y - 86), 3, fill=acc)
                d.text((150, y - 70), card['kicker'], font=fk, fill=acc)
            for i, l in enumerate(tl):
                d.text((150, y + i * 100), l, font=ft, fill=white)
            for i, l in enumerate(sl):
                d.text((150, y + len(tl) * 100 + 30 + i * 46), l, font=fs, fill=soft)
        # a soft dark halo keeps white text readable on bright backgrounds
        sh = blank()
        draw(ImageDraw.Draw(sh), True)
        sh = sh.filter(ImageFilter.GaussianBlur(14))
        a = np.array(sh)
        a[..., 3] = (a[..., 3].astype(np.float32) * 0.75).astype(np.uint8)
        im = Image.fromarray(a)
        draw(ImageDraw.Draw(im), False)
        return Layer(im)


# ---------------------------------------------------------------- takes

class Take:
    def __init__(self, takes_dir, name):
        self.video = os.path.join(takes_dir, f'{name}.webm')
        tl_path = os.path.join(takes_dir, f'{name}.timeline.json')
        if not (os.path.exists(self.video) and os.path.exists(tl_path)):
            sys.exit(f'take "{name}" not found in {takes_dir} (expected {name}.webm and {name}.timeline.json)')
        tl = json.load(open(tl_path))
        self.view, self.marks, self.zooms = tl['view'], tl['marks'], tl['zooms']

    def span(self, scene):
        try:
            st = next(m['at'] for m in self.marks if m['scene'] == scene and m['kind'] == 'start')
            en = next(m['at'] for m in self.marks if m['scene'] == scene and m['kind'] == 'end')
        except StopIteration:
            sys.exit(f'scene "{scene}" not in {self.video}; recorded scenes: '
                     + ', '.join(sorted({m["scene"] for m in self.marks})))
        return st, en

    def zoom_at(self):
        sx = W / self.view['width']
        ivs = []
        for i, z in enumerate(self.zooms):
            if z['kind'] != 'in':
                continue
            end = next((y['at'] for y in self.zooms[i + 1:] if y['kind'] == 'out'), 1e9)
            ivs.append((z['at'], end, z['scale'], z['cx'] * sx, z['cy'] * sx))

        def at(t):
            for a, b, s, cx, cy in ivs:
                if a - 0.01 <= t <= b + 0.9:
                    f = ease((t - a) / 0.85) * (1 - ease((t - b) / 0.85))
                    return 1 + (s - 1) * f, W / 2 + (cx - W / 2) * f, H / 2 + (cy - H / 2) * f
            return 1.0, W / 2, H / 2
        return at

    def frames(self, scene, dur, look, max_speed, title=None, t0=0.0):
        st, en = self.span(scene)
        length = en - st
        speed = min(max_speed, max(1.0, length / dur))
        zoom = self.zoom_at()
        proc = subprocess.Popen(
            ['ffmpeg', '-v', 'error', '-ss', f'{st:.3f}', '-i', self.video, '-t', f'{length:.3f}',
             '-vf', f'fps={FPS},scale={W}:{H}:flags=lanczos', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        size = W * H * 3
        idx, cur = -1, np.zeros((H, W, 3), np.uint8)
        nsrc = max(1, int(length * FPS))
        for k in range(int(round(dur * FPS))):
            want = min(int(k * speed), nsrc - 1)
            while idx < want:
                buf = proc.stdout.read(size)
                if len(buf) < size:
                    break
                cur = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
                idx += 1
            z, cx, cy = zoom(st + min(k / FPS * speed, length))
            if z > 1.001:
                tx = min(0.0, max(W - W * z, W / 2 - cx * z))
                ty = min(0.0, max(H - H * z, H / 2 - cy * z))
                img = cv2.warpAffine(cur, np.float32([[z, 0, tx], [0, z, ty]]), (W, H), flags=cv2.INTER_CUBIC)
            else:
                img = cur
            yield look.framed(img, title, t0 + k / FPS)
        proc.stdout.close()
        proc.wait()


# ---------------------------------------------------------------- captions and outputs

def chunks(text, maxw=12):
    out, cur = [], []
    for w in text.split():
        cur.append(w)
        if len(cur) >= maxw or (re.search(r'[.!?:]$', w) and len(cur) >= 4) or (w.endswith(',') and len(cur) >= 8):
            out.append(' '.join(cur))
            cur = []
    if cur:
        if out and len(cur) <= 2:
            out[-1] += ' ' + ' '.join(cur)
        else:
            out.append(' '.join(cur))
    return out


def stamp(t, sep):
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f'{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)) % 1000:03d}'


def select(board, cut):
    cuts = board.get('cuts') or {'full': '*'}
    if cut not in cuts:
        sys.exit(f'cut "{cut}" not in storyboard cuts: {", ".join(cuts)}')
    spec = cuts[cut]
    shots = board['shots']
    if spec == '*':
        return shots
    by_id = {s['id']: s for s in shots}
    missing = [i for i in spec if i not in by_id]
    if missing:
        sys.exit(f'cut "{cut}" names unknown shots: {", ".join(missing)}')
    return [by_id[i] for i in spec]


def render_cut(board, cut, args, voice, look, takes):
    shots = select(board, cut)
    out_mp4 = os.path.join(args.out, f'{cut}.mp4')
    tmp = tempfile.mkdtemp(prefix='democut-')
    enc = subprocess.Popen(
        ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{W}x{H}', '-r', str(FPS),
         '-i', '-', '-c:v', 'libx264', '-preset', args.preset, '-crf', '20', '-pix_fmt', 'yuv420p',
         os.path.join(tmp, 'v.mp4')], stdin=subprocess.PIPE)
    t, prev, chapter = 0.0, None, None
    audio, cues, chapters, sheet = [], [], [], []
    for i, shot in enumerate(shots):
        text = shot.get(f'say_{cut}', shot.get('say', ''))
        vo = voice.say(text) if text.strip() else np.zeros(int(SR * 1.2), np.float32)
        vlen = len(vo) / SR
        if 'card' in shot:
            card = shot['card']
            dur = vlen + LEAD + 1.0
            lay = look.card(card)

            def card_frames(n=int(round(dur * FPS)), lay=lay, t0=t):
                for k in range(n):
                    f = look.backdrop(t0 + k / FPS).copy()
                    op = ease(k / FPS / 0.7)
                    lay.blend(f, op, int((1 - op) * 24))
                    yield f
            frames, overlay = card_frames(), None
            if card.get('chapter', True):
                chapter = card.get('chapter_title') or card.get('title')
                chapters.append((t, chapter))
            show_caps = bool(card.get('captions', False))
        else:
            if shot['take'] not in takes:
                takes[shot['take']] = Take(args.takes, shot['take'])
            take = takes[shot['take']]
            st, en = take.span(shot['scene'])
            dur = max(vlen + LEAD + TAIL, (en - st) / args.max_speed)
            tcfg = board.get('takes', {}).get(shot['take'], {})
            frames = take.frames(shot['scene'], dur, look, args.max_speed, tcfg.get('window_title'), t)
            overlay = look.badge(tcfg, shot.get('chapter', chapter))
            show_caps = True
        parts = chunks(text) if text.strip() else []
        total = sum(len(p) for p in parts) or 1
        ct, caps = LEAD, []
        for j, p in enumerate(parts):
            cl = vlen * len(p) / total
            # each caption stays until the next one starts; the last one lingers a little
            caps.append((t + ct, t + ct + cl + (0.15 if j == len(parts) - 1 else 0),
                         look.caption(p, shot.get('note')) if show_caps else None))
            cues.append((t + ct, t + ct + cl, p))
            ct += cl
        audio.append((t + LEAD, vo))
        n, last = 0, None
        for f in frames:
            now = t + n / FPS
            if overlay:
                overlay.blend(f, ease(n / FPS / 0.4))
            for c0, c1, lay in caps:
                if lay and c0 <= now < c1:
                    lay.blend(f)
            if prev is not None and n < XFADE * FPS:
                a = ease(n / (XFADE * FPS))
                f = cv2.addWeighted(f, a, prev, 1 - a, 0)
            if n == int(min(dur * 0.6, dur - 0.1) * FPS):
                sheet.append((shot['id'], f.copy()))
            enc.stdin.write(f.tobytes())
            last = f
            n += 1
        prev = last
        t += n / FPS
        log(f'{cut} {i + 1:02d}/{len(shots)} {shot["id"]}: {n / FPS:.1f}s (voice {vlen:.1f}s)')
    enc.stdin.close()
    enc.wait()

    mix = np.zeros(int(np.ceil((t + 1) * SR)), np.float32)
    for at, v in audio:
        s = int(at * SR)
        mix[s:s + len(v)] += v[:max(0, len(mix) - s)]
    with wave.open(os.path.join(tmp, 'a.wav'), 'w') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(mix * 0.95, -1, 1) * 32767).astype(np.int16).tobytes())
    with open(os.path.join(tmp, 'meta.txt'), 'w') as m:
        m.write(';FFMETADATA1\ntitle=' + board.get('title', 'Demo').replace('\n', ' ') + '\n')
        for k, (c0, name) in enumerate(chapters):
            c1 = chapters[k + 1][0] if k + 1 < len(chapters) else t
            m.write(f'[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(c0 * 1000)}\nEND={int(c1 * 1000)}\ntitle={name}\n')
    afilter = 'loudnorm=I=-16:TP=-1.5' if voice.engine != 'none' else 'anull'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(tmp, 'v.mp4'), '-i', os.path.join(tmp, 'a.wav'),
                    '-i', os.path.join(tmp, 'meta.txt'), '-map_metadata', '2', '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-af', afilter, '-shortest',
                    '-movflags', '+faststart', out_mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)

    base = os.path.join(args.out, cut)
    with open(base + '.srt', 'w') as f:
        for k, (a, b, c) in enumerate(cues, 1):
            f.write(f'{k}\n{stamp(a, ",")} --> {stamp(b, ",")}\n{c}\n\n')
    with open(base + '.vtt', 'w') as f:
        f.write('WEBVTT\n\n')
        for a, b, c in cues:
            f.write(f'{stamp(a, ".")} --> {stamp(b, ".")}\n{c}\n\n')
    with open(base + '.chapters.txt', 'w') as f:
        for c0, name in chapters:
            f.write(f'{int(c0 // 60)}:{int(c0 % 60):02d} {name}\n')
    json.dump({'duration': round(t, 2), 'chapters': [{'at': round(a, 2), 'title': n} for a, n in chapters],
               'cues': [{'start': round(a, 2), 'end': round(b, 2), 'text': c} for a, b, c in cues]},
              open(base + '.transcript.json', 'w'), indent=1)
    log(f'{cut}: {t:.1f}s -> {out_mp4}')
    return {'cut': cut, 'duration': t, 'chapters': chapters, 'cues': cues, 'sheet': sheet}


def write_sheet(results, path):
    tiles = [(f'{r["cut"]}:{sid}', f) for r in results for sid, f in r['sheet']]
    if not tiles:
        return
    cols, tw, th = 4, 480, 270
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rows * (th + 30)), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    for i, (label, f) in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 30)
        sheet.paste(Image.fromarray(cv2.cvtColor(cv2.resize(f, (tw, th), interpolation=cv2.INTER_AREA),
                                                 cv2.COLOR_BGR2RGB)), (x, y))
        d.text((x + 8, y + th + 6), label, font=font('m', 16), fill=(230, 230, 230))
    sheet.save(path)
    log(f'contact sheet -> {path}')


def write_gif(args, cut, rng):
    src = os.path.join(args.out, f'{cut}.mp4')
    out = os.path.join(args.out, f'{cut}.gif')
    trim = []
    if rng:
        a, b = rng.split('-')
        trim = ['-ss', a, '-to', b]
    vf = 'fps=12,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', *trim, '-i', src, '-vf', vf, '-loop', '0', out], check=True)
    log(f'gif -> {out} ({os.path.getsize(out) / 1e6:.1f} MB)')


def write_player(board, results, out_dir):
    tpl = open(os.path.join(KIT, 'player.html')).read()
    data = {'title': board.get('title', 'Demo'), 'description': board.get('description', ''),
            'cuts': [{'name': r['cut'], 'label': board.get('cut_labels', {}).get(r['cut'], r['cut']),
                      'duration': round(r['duration'], 1),
                      'chapters': [{'at': round(a, 2), 'title': n} for a, n in r['chapters']],
                      'cues': [{'start': round(a, 2), 'end': round(b, 2), 'text': c} for a, b, c in r['cues']]}
                     for r in results]}
    page = tpl.replace('{{TITLE}}', html.escape(data['title'])).replace(
        '{{DATA}}', json.dumps(data).replace('</', '<\\/'))
    open(os.path.join(out_dir, 'index.html'), 'w').write(page)
    log(f'player -> {os.path.join(out_dir, "index.html")}')


def write_poster(look, board, out_dir):
    shots = board['shots']
    card = next((s['card'] for s in shots if 'card' in s), {'title': board.get('title', 'Demo')})
    f = look.backdrop().copy()
    look.card(card).blend(f)
    cv2.imwrite(os.path.join(out_dir, 'poster.png'), f)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('storyboard')
    ap.add_argument('--takes', required=True, help='folder with <take>.webm + <take>.timeline.json from the director')
    ap.add_argument('--out', required=True)
    ap.add_argument('--cut', action='append', help='cut(s) to render; default: every cut in the storyboard')
    ap.add_argument('--tts', help='override voice.engine: kokoro | none | command')
    ap.add_argument('--gif', help='also write CUT.gif for the README (e.g. --gif short)')
    ap.add_argument('--gif-range', help='seconds, e.g. 3-13')
    ap.add_argument('--sheet', action='store_true', help='write contact-sheet.png (one frame per shot) for review')
    ap.add_argument('--max-speed', type=float, default=1.7)
    ap.add_argument('--preset', default='medium', help='x264 preset (ultrafast for drafts)')
    ap.add_argument('--cache', default=os.path.join(os.path.expanduser('~'), '.cache', 'democut', 'tts'))
    args = ap.parse_args()
    if not shutil.which('ffmpeg'):
        sys.exit('ffmpeg not found on PATH')
    board = json.load(open(args.storyboard))
    os.makedirs(args.out, exist_ok=True)
    if not os.path.isabs(args.takes):
        args.takes = os.path.abspath(args.takes)
    look = Look(board.get('theme'), os.path.dirname(os.path.abspath(args.storyboard)))
    voice = Voice(board.get('voice'), args.tts, args.cache)
    takes = {}
    cuts = args.cut or list((board.get('cuts') or {'full': '*'}).keys())
    results = [render_cut(board, c, args, voice, look, takes) for c in cuts]
    write_poster(look, board, args.out)
    write_player(board, results, args.out)
    if args.sheet:
        write_sheet(results, os.path.join(args.out, 'contact-sheet.png'))
    if args.gif:
        write_gif(args, args.gif, args.gif_range)


if __name__ == '__main__':
    main()
