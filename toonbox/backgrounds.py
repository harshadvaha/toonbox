"""Locations: built-in flat-art backgrounds drawn with code, plus your own uploaded images."""
import json
import random

from PIL import Image, ImageDraw, ImageFilter

from .cast import slug
from .paths import LOCATIONS

OUT = (50, 40, 38)


class _P:
    def __init__(self, W, H, seed=1):
        self.W, self.H = W, H
        self.s = min(W, H)
        self.im = Image.new("RGB", (W, H))
        self.d = ImageDraw.Draw(self.im)
        self.lw = max(2, int(self.s * 0.004))
        self.floor_y = int(H * (0.62 if H > W else 0.66))
        random.seed(seed)

    def r(self, box, fill, outline=OUT, radius=0):
        if radius:
            self.d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=self.lw)
        else:
            self.d.rectangle(box, fill=fill, outline=outline, width=self.lw)

    def room(self, wall, floor, plank=None, base=(120, 90, 70)):
        W, H, fy = self.W, self.H, self.floor_y
        self.d.rectangle((0, 0, W, fy), fill=wall)
        # soft shading at the top of the wall
        for i in range(12):
            a = 1 - i / 12
            c = tuple(int(v * (1 - 0.08 * a)) for v in wall)
            self.d.rectangle((0, int(i * fy * 0.02), W, int((i + 1) * fy * 0.02)), fill=c)
        self.d.rectangle((0, fy, W, H), fill=floor)
        if plank:
            n = 9
            for i in range(1, n):
                y = fy + (H - fy) * (i / n) ** 1.3
                self.d.line((0, y, W, y), fill=plank, width=self.lw)
        self.d.rectangle((0, fy - self.s * 0.025, W, fy), fill=base, outline=OUT, width=self.lw)

    def window(self, x, y, w, h, curtain=None, sky=(178, 220, 240)):
        self.r((x, y, x + w, y + h), (240, 236, 226))
        m = self.s * 0.018
        self.r((x + m, y + m, x + w - m, y + h - m), sky)
        self.d.ellipse((x + w * 0.55, y + h * 0.2, x + w * 0.85, y + h * 0.32), fill=(250, 250, 250))
        self.d.line((x + w / 2, y + m, x + w / 2, y + h - m), fill=(240, 236, 226), width=int(m))
        self.d.line((x + m, y + h / 2, x + w - m, y + h / 2), fill=(240, 236, 226), width=int(m))
        if curtain:
            cw = w * 0.32
            self.r((x - cw * 0.5, y - self.s * 0.03, x + cw * 0.6, y + h * 1.12), curtain)
            self.r((x + w - cw * 0.6, y - self.s * 0.03, x + w + cw * 0.5, y + h * 1.12), curtain)
            self.d.line((x - cw, y - self.s * 0.03, x + w + cw, y - self.s * 0.03), fill=OUT, width=self.lw * 3)

    def frame(self, x, y, w, h, inner=(150, 190, 160)):
        self.r((x, y, x + w, y + h), (150, 105, 70))
        m = w * 0.12
        self.r((x + m, y + m, x + w - m, y + h - m), inner)

    def door(self, x, w, h, col=(176, 122, 80)):
        fy = self.floor_y
        self.r((x, fy - h, x + w, fy), col)
        self.r((x + w * 0.12, fy - h * 0.9, x + w * 0.88, fy - h * 0.55), tuple(int(c * 0.9) for c in col))
        self.r((x + w * 0.12, fy - h * 0.48, x + w * 0.88, fy - h * 0.1), tuple(int(c * 0.9) for c in col))
        self.d.ellipse((x + w * 0.8, fy - h * 0.52, x + w * 0.88, fy - h * 0.46), fill=(230, 200, 90), outline=OUT)

    def plant(self, x, base_y, size):
        s = size
        self.r((x - s * 0.3, base_y - s * 0.5, x + s * 0.3, base_y), (190, 110, 80), radius=int(s * 0.05))
        for dx, dy, rr in ((-0.25, -0.9, 0.35), (0.25, -0.95, 0.32), (0, -1.25, 0.38), (-0.05, -0.7, 0.3)):
            self.d.ellipse((x + dx * s - rr * s, base_y + dy * s - rr * s, x + dx * s + rr * s,
                            base_y + dy * s + rr * s), fill=(90, 160, 95), outline=OUT, width=self.lw)

    def sofa(self, cx, w, col):
        fy = self.floor_y
        h = w * 0.42
        y0 = fy - h * 0.55
        self.r((cx - w / 2, y0 - h * 0.45, cx + w / 2, y0 + h * 0.2), col, radius=int(h * 0.15))
        self.r((cx - w / 2 - h * 0.15, y0 - h * 0.05, cx - w / 2 + h * 0.2, fy + h * 0.25), col, radius=int(h * .1))
        self.r((cx + w / 2 - h * 0.2, y0 - h * 0.05, cx + w / 2 + h * 0.15, fy + h * 0.25), col, radius=int(h * .1))
        self.r((cx - w / 2 + h * 0.2, y0 + h * 0.15, cx + w / 2 - h * 0.2, fy + h * 0.25),
               tuple(min(255, c + 15) for c in col), radius=int(h * 0.08))

    def clouds(self, n, y0, y1):
        for _ in range(n):
            x = random.uniform(0, self.W)
            y = random.uniform(y0, y1)
            r = self.s * random.uniform(0.04, 0.07)
            for dx in (-1.2, 0, 1.2):
                self.d.ellipse((x + dx * r - r, y - r * (0.8 if dx else 1.1), x + dx * r + r, y + r),
                               fill=(255, 255, 255))


def _living(W, H):
    p = _P(W, H, 3)
    p.room((236, 214, 170), (196, 150, 105), (176, 132, 90))
    s, fy = p.s, p.floor_y
    p.window(W * 0.12, fy * 0.28, s * 0.32, s * 0.36, curtain=(214, 96, 86))
    p.frame(W * 0.66, fy * 0.3, s * 0.16, s * 0.2)
    p.door(W * 0.80, s * 0.22, fy * 0.62)
    p.sofa(W * 0.5, s * 0.75, (170, 160, 205))
    p.plant(W * 0.06, fy + s * 0.04, s * 0.18)
    rug = (W * 0.1, fy + (H - fy) * 0.45, W * 0.9, fy + (H - fy) * 0.8)
    p.d.ellipse(rug, fill=(190, 80, 70), outline=OUT, width=p.lw)
    p.d.ellipse((rug[0] + s * 0.04, rug[1] + s * 0.02, rug[2] - s * 0.04, rug[3] - s * 0.02), outline=(240, 200, 120),
                width=p.lw * 2)
    return p.im


def _kitchen(W, H):
    p = _P(W, H, 4)
    p.room((232, 212, 160), (170, 150, 130), None, base=(150, 120, 90))
    s, fy = p.s, p.floor_y
    for i in range(int(W / (s * 0.06)) + 1):  # tiles
        for j in range(4):
            p.d.rectangle((i * s * 0.06, fy * 0.55 + j * s * 0.06, (i + 1) * s * 0.06, fy * 0.55 + (j + 1) * s * 0.06),
                          fill=(225, 232, 228) if (i + j) % 2 else (210, 222, 218), outline=(190, 200, 196))
    p.r((0, fy * 0.12, W, fy * 0.42), (150, 100, 62))  # cabinets
    n = max(3, int(W / (s * 0.22)))
    for i in range(n):
        x = i * W / n
        p.r((x + s * 0.01, fy * 0.14, x + W / n - s * 0.01, fy * 0.40), (168, 116, 74))
    for i, col in enumerate(((200, 120, 40), (230, 170, 50), (120, 70, 40))):
        x = W * (0.2 + 0.08 * i)
        p.r((x, fy * 0.47, x + s * 0.06, fy * 0.55), col, radius=int(s * 0.01))
    p.r((0, fy * 0.78, W, fy * 0.86), (118, 80, 52))  # counter top
    p.r((0, fy * 0.86, W, fy + s * 0.02), (140, 96, 62))
    p.r((W * 0.62, fy * 0.70, W * 0.88, fy * 0.78), (80, 80, 86), radius=int(s * 0.01))  # stove
    p.d.ellipse((W * 0.66, fy * 0.66, W * 0.76, fy * 0.73), fill=(40, 40, 44), outline=OUT)
    p.window(W * 0.62, fy * 0.48, s * 0.22, s * 0.16)
    return p.im


def _bedroom(W, H):
    p = _P(W, H, 5)
    p.room((196, 212, 232), (200, 170, 140), (180, 150, 120))
    s, fy = p.s, p.floor_y
    p.window(W * 0.62, fy * 0.25, s * 0.28, s * 0.3, curtain=(240, 240, 250), sky=(40, 50, 100))
    p.d.ellipse((W * 0.7, fy * 0.3, W * 0.7 + s * 0.06, fy * 0.3 + s * 0.06), fill=(250, 240, 180))
    p.r((W * 0.05, fy - s * 0.28, W * 0.5, fy + s * 0.05), (230, 230, 240), radius=int(s * 0.02))
    p.r((W * 0.03, fy - s * 0.42, W * 0.08, fy + s * 0.08), (140, 100, 70))
    p.r((W * 0.08, fy - s * 0.25, W * 0.2, fy - s * 0.18), (250, 250, 255), radius=int(s * 0.02))
    p.r((W * 0.05, fy - s * 0.14, W * 0.5, fy + s * 0.05), (110, 140, 200), radius=int(s * 0.02))
    p.frame(W * 0.2, fy * 0.28, s * 0.15, s * 0.15, inner=(240, 200, 150))
    return p.im


def _office(W, H):
    p = _P(W, H, 6)
    p.room((218, 222, 222), (150, 160, 165), None, base=(110, 115, 118))
    s, fy = p.s, p.floor_y
    for i in range(int(W / (s * 0.18)) + 1):
        p.d.rectangle((i * s * 0.18 + s * 0.02, s * 0.03, i * s * 0.18 + s * 0.14, s * 0.05), fill=(250, 250, 240))
    p.window(W * 0.1, fy * 0.25, s * 0.5, s * 0.28)
    p.r((W * 0.68, fy * 0.3, W * 0.68 + s * 0.12, fy - s * 0.02), (170, 176, 180))
    for j in range(4):
        p.r((W * 0.68 + s * 0.01, fy * 0.32 + j * s * 0.07, W * 0.68 + s * 0.11, fy * 0.32 + j * s * 0.07 + s * 0.06),
            (190, 196, 200))
    p.plant(W * 0.92, fy + s * 0.03, s * 0.15)
    return p.im


def _classroom(W, H):
    p = _P(W, H, 7)
    p.room((230, 220, 190), (180, 140, 100), (160, 120, 85))
    s, fy = p.s, p.floor_y
    p.r((W * 0.08, fy * 0.22, W * 0.92, fy * 0.62), (50, 90, 70))
    p.d.rectangle((W * 0.08, fy * 0.62, W * 0.92, fy * 0.64), fill=(150, 105, 70))
    p.d.line((W * 0.15, fy * 0.35, W * 0.4, fy * 0.35), fill=(240, 240, 230), width=p.lw * 2)
    p.d.line((W * 0.15, fy * 0.43, W * 0.32, fy * 0.43), fill=(240, 240, 230), width=p.lw * 2)
    p.d.ellipse((W * 0.78, fy * 0.06, W * 0.78 + s * 0.1, fy * 0.06 + s * 0.1), fill=(250, 250, 250), outline=OUT,
                width=p.lw)
    return p.im


def _park(W, H):
    p = _P(W, H, 8)
    fy = p.floor_y
    s = p.s
    for i in range(20):
        c = (150 + i * 3, 205 + i, 240)
        p.d.rectangle((0, fy * i / 20, W, fy * (i + 1) / 20), fill=c)
    p.d.ellipse((W * 0.75, fy * 0.08, W * 0.75 + s * 0.14, fy * 0.08 + s * 0.14), fill=(255, 225, 110))
    p.clouds(4, fy * 0.1, fy * 0.45)
    p.d.ellipse((-W * 0.2, fy - s * 0.18, W * 0.7, fy + s * 0.2), fill=(120, 180, 100))
    p.d.ellipse((W * 0.4, fy - s * 0.12, W * 1.3, fy + s * 0.2), fill=(110, 170, 95))
    p.d.rectangle((0, fy, W, H), fill=(130, 190, 105))
    for x in (0.12, 0.85):
        p.r((W * x - s * 0.03, fy - s * 0.35, W * x + s * 0.03, fy + s * 0.02), (130, 90, 60))
        p.d.ellipse((W * x - s * 0.16, fy - s * 0.62, W * x + s * 0.16, fy - s * 0.28), fill=(80, 150, 80),
                    outline=OUT, width=p.lw)
    p.d.polygon([(W * 0.42, H), (W * 0.58, H), (W * 0.53, fy), (W * 0.47, fy)], fill=(220, 200, 150))
    return p.im


def _street(W, H):
    p = _P(W, H, 9)
    fy = p.floor_y
    s = p.s
    p.d.rectangle((0, 0, W, fy), fill=(190, 225, 240))
    p.clouds(3, fy * 0.05, fy * 0.25)
    x = 0
    cols = [(230, 180, 140), (200, 160, 200), (240, 210, 140), (170, 200, 180), (220, 150, 130)]
    i = 0
    while x < W:
        bw = s * random.uniform(0.25, 0.4)
        bh = fy * random.uniform(0.55, 0.85)
        p.r((x, fy - bh, x + bw, fy), cols[i % len(cols)])
        for wy in range(int(fy - bh + s * 0.05), int(fy - s * 0.12), int(s * 0.1)):
            for wx in (x + bw * 0.2, x + bw * 0.6):
                p.r((wx, wy, wx + bw * 0.2, wy + s * 0.06), (120, 160, 190))
        x += bw
        i += 1
    p.d.rectangle((0, fy, W, fy + (H - fy) * 0.3), fill=(200, 196, 186))
    p.d.rectangle((0, fy + (H - fy) * 0.3, W, H), fill=(90, 92, 98))
    for i in range(6):
        p.d.rectangle((W * i / 5, fy + (H - fy) * 0.62, W * i / 5 + W * 0.08, fy + (H - fy) * 0.66),
                      fill=(240, 230, 150))
    return p.im


def _studio(W, H):
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for i in range(40):
        c = (int(70 + i * 1.5), int(110 + i * 1.6), int(140 + i * 1.4))
        d.rectangle((0, H * i / 40, W, H * (i + 1) / 40), fill=c)
    return im


BUILTIN = {
    "Living room": _living, "Kitchen": _kitchen, "Bedroom": _bedroom, "Office": _office,
    "Classroom": _classroom, "Park": _park, "Street": _street, "Plain studio": _studio,
}


def list_locations():
    names = list(BUILTIN)
    for f in sorted(LOCATIONS.glob("*.json")):
        try:
            names.append(json.loads(f.read_text())["name"])
        except Exception:
            pass
    return names


def add_location(name, src_path):
    name = name.strip() or "My place"
    sid = slug(name)
    base, i = sid, 2
    while (LOCATIONS / f"{sid}.json").exists():
        sid = f"{base}-{i}"
        i += 1
    Image.open(src_path).convert("RGB").save(LOCATIONS / f"{sid}.png")
    (LOCATIONS / f"{sid}.json").write_text(json.dumps({"name": name, "image": f"{sid}.png"}))
    return name


def _uploaded(name):
    for f in LOCATIONS.glob("*.json"):
        meta = json.loads(f.read_text())
        if meta["name"] == name:
            return LOCATIONS / meta["image"]
    return None


def render(name, W, H):
    if name in BUILTIN:
        return BUILTIN[name](W, H)
    path = _uploaded(name)
    if path is None:
        return _studio(W, H)
    im = Image.open(path).convert("RGB")
    sc = max(W / im.width, H / im.height)
    im = im.resize((max(W, round(im.width * sc)), max(H, round(im.height * sc))), Image.LANCZOS)
    x = (im.width - W) // 2
    y = (im.height - H) // 2
    return im.crop((x, y, x + W, y + H))


def floor_ratio(W, H):
    return 0.62 if H > W else 0.66


def preview(name):
    im = render(name, 540, 960)
    return im
