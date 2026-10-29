"""Cartoon emote symbols (!, ?, anger mark, sweat drop, sparkles, ..., heart) drawn with code."""
import math

from PIL import Image, ImageDraw, ImageFont

EMOTES = ["!", "?", "anger", "sweat", "sparkle", "think", "heart", "shock"]
INK = (34, 30, 40, 255)


def _font(size):
    for f in ("/System/Library/Fonts/Supplemental/Arial Black.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
              "/Library/Fonts/Arial Bold.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except Exception:
            continue
    return ImageFont.load_default(size)


def _star(d, cx, cy, r, fill):
    pts = []
    for i in range(8):
        rr = r if i % 2 == 0 else r * 0.32
        a = math.pi / 4 * i - math.pi / 2
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill, outline=INK, width=max(2, int(r * 0.09)))


_cache = {}


def draw(name, size):
    key = (name, size)
    if key in _cache:
        return _cache[key]
    S = 3
    W = size * S
    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    lw = max(3, W // 22)
    c = W / 2
    if name in ("!", "?", "shock"):
        col = {"!": (240, 70, 70, 255), "?": (70, 130, 240, 255), "shock": (250, 200, 40, 255)}[name]
        txt = {"!": "!", "?": "?", "shock": "!!"}[name]
        f = _font(int(W * 0.8))
        d.text((c, c), txt, font=f, fill=col, anchor="mm", stroke_width=lw, stroke_fill=INK)
    elif name == "anger":
        red = (230, 50, 60, 255)
        for ang in (45, 135, 225, 315):
            a = math.radians(ang)
            x, y = c + W * 0.22 * math.cos(a), c + W * 0.22 * math.sin(a)
            d.arc((x - W * 0.16, y - W * 0.16, x + W * 0.16, y + W * 0.16), ang + 90, ang + 270, fill=red,
                  width=int(lw * 1.8))
    elif name == "sweat":
        blue = (120, 190, 250, 255)
        d.ellipse((c - W * 0.22, c - W * 0.05, c + W * 0.22, c + W * 0.39), fill=blue, outline=INK, width=lw)
        d.polygon([(c, c - W * 0.40), (c - W * 0.19, c + W * 0.06), (c + W * 0.19, c + W * 0.06)], fill=blue)
        d.line([(c, c - W * 0.40), (c - W * 0.20, c + W * 0.05)], fill=INK, width=lw)
        d.line([(c, c - W * 0.40), (c + W * 0.20, c + W * 0.05)], fill=INK, width=lw)
        d.ellipse((c - W * 0.10, c + W * 0.08, c - W * 0.02, c + W * 0.2), fill=(255, 255, 255, 230))
    elif name == "sparkle":
        _star(d, c - W * 0.12, c + W * 0.05, W * 0.3, (255, 215, 60, 255))
        _star(d, c + W * 0.28, c - W * 0.25, W * 0.15, (255, 235, 120, 255))
    elif name == "think":
        for i, x in enumerate((0.22, 0.5, 0.78)):
            r = W * 0.08
            d.ellipse((W * x - r, c - r, W * x + r, c + r), fill=INK)
    elif name == "heart":
        pink = (240, 90, 130, 255)
        r = W * 0.2
        d.ellipse((c - 2 * r, c - 1.5 * r, c, c + 0.5 * r), fill=pink)
        d.ellipse((c, c - 1.5 * r, c + 2 * r, c + 0.5 * r), fill=pink)
        d.polygon([(c - 1.93 * r, c - 0.2 * r), (c + 1.93 * r, c - 0.2 * r), (c, c + 2.1 * r)], fill=pink)
    out = im.resize((size, size), Image.LANCZOS)
    _cache[key] = out
    return out


def animated(name, size, p):
    """Emote at progress p (0..1): pops in, wobbles, fades out."""
    if p < 0 or p > 1:
        return None
    if p < 0.15:
        k = p / 0.15
        s = 1.25 * math.sin(k * math.pi / 2) if k < 1 else 1
        s = max(0.05, min(s, 1.25)) if k < 0.8 else 1 + 0.25 * (1 - k) / 0.2
    else:
        s = 1.0
    sz = max(4, int(size * s))
    im = draw(name, sz)
    if p > 0.8:
        a = (1 - (p - 0.8) / 0.2)
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * a)))
    return im
