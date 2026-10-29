"""Props library: furniture, objects, pets — all drawn in the same flat outlined style as the characters.

Each prop has a layer and the words that make the director bring it in:
  front  - in front of the characters (desk, table, counter); hides legs like a real set
  back   - behind the characters, on the floor (chair, sofa, bed, plant, TV …)
  floor  - small things standing near the characters (dog, cat, suitcase, box …)
  hand   - held in a hand (phone, cup, book, money …)
  worn   - on the character (necklace, cap, crown, headphones)
To add a new prop: write a small draw function below and add one line to PROPS,
or upload a PNG in the app (it is scaled to the characters and used the same way).
Units: 1 = one character height; (0, 0) = where the prop touches the floor (or the hand point).
"""
import json
import math

import skia

from .paths import LIBRARY

INK = (28, 26, 34)
OW = 0.011
PROP_DIR = LIBRARY / "props"
PROP_DIR.mkdir(parents=True, exist_ok=True)


def _p(c, a=255):
    return skia.Paint(Color=skia.ColorSetARGB(a, *c), AntiAlias=True)


def _s(c, w):
    return skia.Paint(Color=skia.ColorSetARGB(255, *c), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                      StrokeWidth=w, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)


def _fo(cv, path, col, ow=OW):
    cv.drawPath(path, _p(col))
    cv.drawPath(path, _s(INK, ow))


def rect(cv, l, t, r, b, col, rad=0.0, ow=OW):
    p = skia.Path()
    if rad:
        p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(l, t, r, b), rad, rad))
    else:
        p.addRect(skia.Rect.MakeLTRB(l, t, r, b))
    _fo(cv, p, col, ow)


def oval(cv, cx, cy, rx, ry, col, ow=OW):
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    _fo(cv, p, col, ow)


def poly(cv, pts, col, ow=OW, close=True):
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    if close:
        p.close()
        _fo(cv, p, col, ow)
    else:
        cv.drawPath(p, _s(INK, ow))


def dark(c, k=0.82):
    return tuple(max(0, min(255, int(v * k))) for v in c)


# ============================================================ front props (span the width, hide lower bodies)
def desk(cv, W, top, col=(214, 170, 112), laptops=(), monitor=(), mugs=()):
    """W = width in units, top = desk top height above floor."""
    rect(cv, -W / 2, -top - 0.03, W / 2, -top + 0.02, col, 0.01)
    rect(cv, -W / 2 + 0.02, -top + 0.02, W / 2 - 0.02, 0.4, dark(col, 0.86))
    cv.drawLine(-W / 2 + 0.02, -top + 0.12, W / 2 - 0.02, -top + 0.12, _s(dark(col, 0.7), OW))
    for x in laptops:
        laptop_back(cv, x, -top - 0.03)
    for x in monitor:
        monitor_back(cv, x, -top - 0.03)
    for x in mugs:
        mug(cv, x, -top - 0.03)


def laptop_back(cv, x, y):
    poly(cv, [(x - 0.17, y - 0.01), (x - 0.15, y - 0.22), (x + 0.15, y - 0.22), (x + 0.17, y - 0.01)], (64, 66, 74))
    rect(cv, x - 0.2, y - 0.02, x + 0.2, y + 0.005, (90, 92, 100), 0.005)
    oval(cv, x, y - 0.12, 0.025, 0.025, (220, 222, 230), OW * 0.7)


def monitor_back(cv, x, y):
    rect(cv, x - 0.02, y - 0.1, x + 0.02, y, (70, 70, 80))
    rect(cv, x - 0.2, y - 0.3, x + 0.2, y - 0.08, (60, 62, 70), 0.012)


def mug(cv, x, y):
    rect(cv, x - 0.03, y - 0.07, x + 0.03, y, (240, 240, 245), 0.008)
    p = skia.Path()
    p.addArc(skia.Rect.MakeLTRB(x + 0.015, y - 0.06, x + 0.06, y - 0.02), -90, 180)
    cv.drawPath(p, _s(INK, OW))


def table(cv, W, top, col=(176, 120, 82), **_):
    rect(cv, -W / 2, -top - 0.025, W / 2, -top + 0.015, col, 0.012)
    rect(cv, -W / 2 + 0.06, -top + 0.015, -W / 2 + 0.1, 0.0, dark(col))
    rect(cv, W / 2 - 0.1, -top + 0.015, W / 2 - 0.06, 0.0, dark(col))


def counter(cv, W, top, col=(236, 236, 240), **_):
    rect(cv, -W / 2, -top - 0.03, W / 2, -top + 0.01, (120, 124, 132))
    rect(cv, -W / 2 + 0.01, -top + 0.01, W / 2 - 0.01, 0.4, col)
    n = max(2, int(W / 0.35))
    for i in range(1, n):
        x = -W / 2 + W * i / n
        cv.drawLine(x, -top + 0.03, x, 0.4, _s(INK, OW * 0.8))
        oval(cv, x - 0.03, -top + 0.12, 0.01, 0.01, (150, 150, 160), OW * 0.6)


# ============================================================ back props (behind characters, floor anchored)
def chair(cv, col=(70, 74, 86)):
    rect(cv, -0.12, -0.62, 0.12, -0.32, col, 0.04)
    rect(cv, -0.015, -0.32, 0.015, -0.12, (110, 110, 118))
    rect(cv, -0.14, -0.3, 0.14, -0.25, dark(col), 0.02)
    for dx in (-0.12, 0.0, 0.12):
        cv.drawLine(0, -0.1, dx, -0.02, _s(INK, OW * 2.5))
        oval(cv, dx, -0.02, 0.02, 0.02, (40, 40, 46))


def wooden_chair(cv, col=(170, 112, 70)):
    rect(cv, -0.12, -0.7, 0.12, -0.36, col, 0.02)
    rect(cv, -0.09, -0.64, 0.09, -0.44, dark(col, 0.9), 0.01)
    rect(cv, -0.14, -0.36, 0.14, -0.31, dark(col), 0.01)
    for x in (-0.12, 0.1):
        rect(cv, x, -0.31, x + 0.025, 0.0, dark(col))


def sofa(cv, col=(96, 140, 170), w=1.1):
    rect(cv, -w / 2, -0.62, w / 2, -0.3, col, 0.06)
    rect(cv, -w / 2 - 0.08, -0.42, -w / 2 + 0.08, -0.05, dark(col, 0.9), 0.04)
    rect(cv, w / 2 - 0.08, -0.42, w / 2 + 0.08, -0.05, dark(col, 0.9), 0.04)
    rect(cv, -w / 2 + 0.06, -0.33, w / 2 - 0.06, -0.12, tuple(min(255, c + 18) for c in col), 0.03)
    rect(cv, -w / 2 + 0.04, -0.12, w / 2 - 0.04, -0.04, dark(col), 0.02)


def bed(cv, col=(240, 240, 246), w=1.2):
    rect(cv, -w / 2 - 0.04, -0.62, -w / 2 + 0.03, 0.0, (150, 104, 70), 0.02)
    rect(cv, -w / 2, -0.3, w / 2, -0.12, col, 0.03)
    rect(cv, -w / 2 + 0.02, -0.4, -w / 2 + 0.3, -0.29, (255, 255, 255), 0.04)
    rect(cv, -w / 2 + 0.25, -0.32, w / 2, -0.2, (120, 150, 210), 0.03)
    rect(cv, -w / 2, -0.12, w / 2, -0.04, (150, 104, 70))


def plant(cv, s=1.0):
    rect(cv, -0.07 * s, -0.14 * s, 0.07 * s, 0, (196, 110, 76), 0.015)
    for dx, dy, r in ((-0.06, -0.22, 0.07), (0.06, -0.24, 0.065), (0, -0.32, 0.08), (-0.02, -0.18, 0.06)):
        oval(cv, dx * s, dy * s, r * s, r * s * 1.1, (88, 160, 96))


def lamp(cv):
    rect(cv, -0.06, -0.02, 0.06, 0.0, (60, 60, 66))
    cv.drawLine(0, -0.02, 0, -0.6, _s(INK, OW * 2.2))
    poly(cv, [(-0.1, -0.58), (-0.06, -0.72), (0.06, -0.72), (0.1, -0.58)], (250, 226, 150))


def tv(cv):
    rect(cv, -0.32, -0.25, 0.32, 0.0, (140, 98, 66), 0.02)
    rect(cv, -0.03, -0.3, 0.03, -0.25, (50, 50, 56))
    rect(cv, -0.34, -0.66, 0.34, -0.29, (40, 42, 50), 0.02)
    rect(cv, -0.31, -0.63, 0.31, -0.32, (80, 120, 170), 0.01)


def bookshelf(cv):
    rect(cv, -0.25, -0.95, 0.25, 0.0, (150, 104, 70), 0.01)
    cols = [(200, 80, 80), (80, 130, 200), (230, 190, 80), (90, 170, 110), (160, 100, 180)]
    for r in range(4):
        y = -0.92 + r * 0.23
        cv.drawLine(-0.25, y + 0.2, 0.25, y + 0.2, _s(INK, OW))
        x = -0.22
        i = r
        while x < 0.18:
            w = 0.04 + 0.015 * ((i * 7) % 3)
            rect(cv, x, y + 0.05 + 0.02 * (i % 2), x + w, y + 0.2, cols[i % 5], 0.004, OW * 0.7)
            x += w + 0.008
            i += 1


def fridge(cv):
    rect(cv, -0.22, -1.0, 0.22, 0.0, (232, 236, 240), 0.03)
    cv.drawLine(-0.22, -0.62, 0.22, -0.62, _s(INK, OW))
    rect(cv, 0.14, -0.9, 0.165, -0.7, (170, 170, 180), 0.01, OW * 0.7)
    rect(cv, 0.14, -0.55, 0.165, -0.3, (170, 170, 180), 0.01, OW * 0.7)


def door(cv, col=(170, 116, 76)):
    rect(cv, -0.24, -1.1, 0.24, 0.0, col, 0.01)
    rect(cv, -0.18, -1.02, 0.18, -0.62, dark(col, 0.9), 0.01, OW * 0.8)
    rect(cv, -0.18, -0.55, 0.18, -0.08, dark(col, 0.9), 0.01, OW * 0.8)
    oval(cv, 0.16, -0.55, 0.025, 0.025, (232, 196, 80))


def whiteboard(cv):
    rect(cv, -0.45, -1.15, 0.45, -0.6, (250, 250, 252), 0.015)
    for i, w in enumerate((0.5, 0.35, 0.6)):
        cv.drawLine(-0.38, -1.05 + i * 0.12, -0.38 + w, -1.05 + i * 0.12, _s((70, 110, 200), OW * 1.4))


# ============================================================ floor items (near characters)
def dog(cv, t=0.0, col=(236, 222, 200), spot=(150, 110, 80), walking=False):
    bob = abs(math.sin(t * 9)) * 0.012 if walking else 0
    cv.save()
    cv.translate(0, -bob)
    wag = math.sin(t * 14) * 18
    for i, dx in enumerate((-0.12, -0.07, 0.07, 0.12)):
        sw = math.sin(t * 9 + i * math.pi) * 0.025 if walking else 0
        rect(cv, dx - 0.018 + sw, -0.1, dx + 0.018 + sw, 0.0, col, 0.012)
    cv.save()
    cv.translate(-0.15, -0.17)
    cv.rotate(-30 + wag)
    rect(cv, -0.015, -0.1, 0.015, 0.0, col, 0.012)
    cv.restore()
    oval(cv, 0, -0.15, 0.17, 0.075, col)
    oval(cv, 0.03, -0.17, 0.05, 0.03, spot, OW * 0.6)
    oval(cv, 0.16, -0.25, 0.085, 0.075, col)
    oval(cv, 0.1, -0.27, 0.03, 0.06, spot)
    oval(cv, 0.22, -0.23, 0.04, 0.03, col, OW * 0.8)
    oval(cv, 0.255, -0.24, 0.014, 0.012, INK, 0.001)
    oval(cv, 0.175, -0.27, 0.011, 0.014, INK, 0.001)
    cv.restore()


def cat(cv, t=0.0, col=(120, 120, 130), walking=False):
    for dx in (-0.08, 0.08):
        rect(cv, dx - 0.015, -0.08, dx + 0.015, 0.0, col, 0.01)
    p = skia.Path()
    p.moveTo(-0.12, -0.12)
    p.quadTo(-0.25, -0.2 + math.sin(t * 4) * 0.03, -0.2, -0.32)
    cv.drawPath(p, _s(INK, 0.03))
    cv.drawPath(p, _s(col, 0.018))
    oval(cv, 0, -0.12, 0.13, 0.06, col)
    oval(cv, 0.12, -0.2, 0.065, 0.06, col)
    poly(cv, [(0.07, -0.24), (0.08, -0.3), (0.11, -0.25)], col, OW * 0.8)
    poly(cv, [(0.13, -0.25), (0.17, -0.3), (0.18, -0.23)], col, OW * 0.8)
    oval(cv, 0.1, -0.2, 0.01, 0.014, INK, 0.001)
    oval(cv, 0.15, -0.2, 0.01, 0.014, INK, 0.001)


def suitcase(cv, col=(200, 80, 70)):
    rect(cv, -0.03, -0.32, 0.03, -0.26, (60, 60, 66), 0.01)
    rect(cv, -0.12, -0.27, 0.12, 0.0, col, 0.025)
    for x in (-0.06, 0.06):
        cv.drawLine(x, -0.25, x, -0.02, _s(dark(col, 0.7), OW * 1.3))


def box(cv, col=(204, 160, 104)):
    rect(cv, -0.12, -0.2, 0.12, 0.0, col, 0.005)
    cv.drawLine(-0.12, -0.15, 0.12, -0.15, _s(dark(col, 0.75), OW))
    rect(cv, -0.03, -0.2, 0.03, -0.15, (240, 220, 180), 0.0, OW * 0.6)


def bag(cv, col=(80, 120, 180)):
    p = skia.Path()
    p.addArc(skia.Rect.MakeLTRB(-0.06, -0.28, 0.06, -0.16), 180, 180)
    cv.drawPath(p, _s(INK, 0.02))
    rect(cv, -0.1, -0.22, 0.1, 0.0, col, 0.03)


def ball(cv, col=(232, 90, 80)):
    oval(cv, 0, -0.06, 0.06, 0.06, col)
    cv.drawLine(-0.06, -0.06, 0.06, -0.06, _s(INK, OW * 0.8))


# ============================================================ hand props (drawn at the hand, inside the character)
def phone(cv, ow):
    rect(cv, -0.018, -0.05, 0.018, 0.012, (245, 245, 250), 0.008, ow * 0.8)


def cup(cv, ow):
    rect(cv, -0.022, -0.06, 0.022, 0.0, (240, 240, 244), 0.006, ow * 0.8)
    rect(cv, -0.022, -0.06, 0.022, -0.045, (150, 96, 60), 0.004, ow * 0.6)


def book(cv, ow):
    rect(cv, -0.045, -0.07, 0.045, 0.0, (80, 120, 190), 0.005, ow * 0.8)
    cv.drawLine(0, -0.07, 0, 0, _s(INK, ow * 0.7))


def paper(cv, ow):
    rect(cv, -0.035, -0.09, 0.035, 0.0, (255, 255, 255), 0.002, ow * 0.7)
    for i in range(3):
        cv.drawLine(-0.022, -0.07 + i * 0.02, 0.022, -0.07 + i * 0.02, _s((150, 150, 160), ow * 0.6))


def money(cv, ow):
    for i in range(3):
        rect(cv, -0.045 + i * 0.006, -0.03 - i * 0.008, 0.045 + i * 0.006, 0.0 - i * 0.008, (120, 190, 120), 0.004,
             ow * 0.6)


def flower(cv, ow):
    cv.drawLine(0, 0, 0, -0.1, _s((70, 140, 80), ow * 1.3))
    for i in range(5):
        a = i * 2 * math.pi / 5
        oval(cv, math.cos(a) * 0.022, -0.11 + math.sin(a) * 0.022, 0.016, 0.016, (240, 110, 150), ow * 0.6)
    oval(cv, 0, -0.11, 0.012, 0.012, (250, 210, 80), ow * 0.5)


def gift(cv, ow):
    rect(cv, -0.04, -0.07, 0.04, 0.0, (220, 70, 90), 0.004, ow * 0.8)
    rect(cv, -0.008, -0.07, 0.008, 0.0, (250, 220, 90), 0.0, ow * 0.5)


def keys(cv, ow):
    cv.drawCircle(0, -0.02, 0.014, _s(INK, ow))
    rect(cv, -0.004, -0.05, 0.004, -0.03, (220, 190, 80), 0.002, ow * 0.5)


def necklace_hand(cv, ow):
    p = skia.Path()
    p.addArc(skia.Rect.MakeLTRB(-0.03, -0.01, 0.03, 0.07), 0, 180)
    cv.drawPath(p, _s((240, 200, 80), ow * 1.4))
    oval(cv, 0, 0.075, 0.012, 0.012, (120, 200, 230), ow * 0.6)


# ============================================================ worn props (drawn on the character)
def necklace_worn(cv, neck, ow):
    x, y = neck
    p = skia.Path()
    p.moveTo(x - 0.03, y + 0.005)
    p.quadTo(x, y + 0.07, x + 0.03, y + 0.005)
    cv.drawPath(p, _s((240, 200, 80), ow * 1.4))
    oval(cv, x, y + 0.05, 0.011, 0.011, (120, 200, 230), ow * 0.6)


def cap_worn(cv, R, ow, col=(60, 110, 190)):
    p = skia.Path()
    p.moveTo(-R * 1.02, -R * 0.3)
    p.cubicTo(-R * 1.0, -R * 1.35, R * 1.0, -R * 1.35, R * 1.02, -R * 0.3)
    p.close()
    _fo(cv, p, col, ow)
    rect(cv, R * 0.2, -R * 0.42, R * 1.5, -R * 0.26, dark(col), R * 0.08, ow)


def crown_worn(cv, R, ow):
    poly(cv, [(-R * 0.55, -R * 0.85), (-R * 0.6, -R * 1.35), (-R * 0.28, -R * 1.1), (0, -R * 1.45),
              (R * 0.28, -R * 1.1), (R * 0.6, -R * 1.35), (R * 0.55, -R * 0.85)], (246, 196, 60), ow)


def headphones_worn(cv, R, ow):
    p = skia.Path()
    p.addArc(skia.Rect.MakeLTRB(-R * 1.08, -R * 1.2, R * 1.08, R * 0.6), 180, 180)
    cv.drawPath(p, _s(INK, R * 0.12))
    for sg in (-1, 1):
        rect(cv, sg * R * 1.05 - R * 0.14, -R * 0.35, sg * R * 1.05 + R * 0.14, R * 0.15, (60, 60, 70), R * 0.08, ow)


# ============================================================ registry
#  name: (layer, draw, words that bring it in)
PROPS = {
    # front
    "desk":         ("front", desk, ["laptop", "computer", "office", "work", "meeting", "email", "boss", "desk"]),
    "table":        ("front", table, ["dinner", "lunch", "breakfast", "eat", "food", "khana", "table"]),
    "counter":      ("front", counter, ["cook", "kitchen", "chai", "tea", "coffee"]),
    # back
    "office chair": ("back", chair, ["chair", "sit", "office"]),
    "chair":        ("back", wooden_chair, ["chair", "sit", "baitho"]),
    "sofa":         ("back", sofa, ["sofa", "couch", "tv", "relax", "movie"]),
    "bed":          ("back", bed, ["bed", "sleep", "tired", "night", "neend", "so ja"]),
    "plant":        ("back", plant, ["plant", "garden"]),
    "lamp":         ("back", lamp, ["lamp", "light"]),
    "tv":           ("back", tv, ["tv", "television", "match", "movie", "netflix"]),
    "bookshelf":    ("back", bookshelf, ["book", "study", "padhai", "exam", "library"]),
    "fridge":       ("back", fridge, ["fridge", "hungry", "bhook", "ice cream", "cold drink"]),
    "door":         ("back", door, ["door", "knock", "leave", "out", "come in", "darwaza"]),
    "whiteboard":   ("back", whiteboard, ["class", "teacher", "presentation", "board", "explain"]),
    # floor
    "dog":          ("floor", dog, ["dog", "puppy", "doggy", "kutta", "woof", "ghost"]),
    "cat":          ("floor", cat, ["cat", "kitty", "billi", "meow"]),
    "suitcase":     ("floor", suitcase, ["pack", "suitcase", "travel", "trip", "luggage", "move out", "leaving"]),
    "box":          ("floor", box, ["box", "parcel", "delivery", "amazon", "order"]),
    "bag":          ("floor", bag, ["bag", "school", "college"]),
    "ball":         ("floor", ball, ["ball", "play", "cricket", "football"]),
    # hand
    "phone":        ("hand", phone, ["phone", "call", "text", "message", "whatsapp", "instagram", "selfie", "hello?"]),
    "cup":          ("hand", cup, ["coffee", "tea", "chai", "drink", "cup"]),
    "book":         ("hand", book, ["book", "read", "study"]),
    "paper":        ("hand", paper, ["report", "letter", "paper", "result", "marks", "bill", "notice"]),
    "money":        ("hand", money, ["money", "paise", "rupees", "cash", "salary", "pay", "paisa", "₹"]),
    "flower":       ("hand", flower, ["flower", "rose", "propose", "valentine"]),
    "gift":         ("hand", gift, ["gift", "present", "birthday", "surprise"]),
    "keys":         ("hand", keys, ["keys", "car", "bike", "chabi"]),
    "necklace":     ("hand", necklace_hand, []),
    # worn
    "necklace (worn)": ("worn", necklace_worn, ["necklace", "chain", "jewellery", "jewelry"]),
    "cap":          ("worn", cap_worn, ["cap", "hat"]),
    "crown":        ("worn", crown_worn, ["king", "queen", "crown", "princess"]),
    "headphones":   ("worn", headphones_worn, ["music", "song", "headphones", "earphones", "podcast"]),
}

# what each built-in location brings by default
LOCATION_KIT = {
    "Office": {"front": "desk", "back": ["office chair"], "desk_items": "laptops"},
    "Classroom": {"front": "desk", "back": ["whiteboard"], "desk_items": "none"},
    "Kitchen": {"front": "counter", "back": ["fridge"]},
    "Living room": {"back": ["plant"]},
    "Bedroom": {"back": ["lamp"]},
    "Park": {}, "Street": {}, "Plain studio": {},
}


def list_props():
    names = list(PROPS)
    for f in sorted(PROP_DIR.glob("*.json")):
        try:
            names.append(json.loads(f.read_text())["name"])
        except Exception:
            pass
    return names


def uploaded():
    out = {}
    for f in sorted(PROP_DIR.glob("*.json")):
        try:
            m = json.loads(f.read_text())
            m["path"] = str(PROP_DIR / m["image"])
            out[m["name"]] = m
        except Exception:
            pass
    return out


def add_prop(name, image_path, layer="floor", words="", size=0.3):
    """Save a user PNG as a prop. size = height in character heights."""
    from PIL import Image
    from .cast import slug
    name = (name or "My prop").strip()
    sid = slug(name)
    im = Image.open(image_path).convert("RGBA")
    bb = im.getchannel("A").getbbox()
    if bb:
        im = im.crop(bb)
    im.save(PROP_DIR / f"{sid}.png")
    meta = {"name": name, "image": f"{sid}.png", "layer": layer, "size": float(size),
            "words": [w.strip().lower() for w in (words or "").split(",") if w.strip()]}
    (PROP_DIR / f"{sid}.json").write_text(json.dumps(meta, indent=2))
    return name


def layer_of(name):
    if name in PROPS:
        return PROPS[name][0]
    m = uploaded().get(name)
    return m["layer"] if m else "floor"


def keywords():
    """word -> prop name, built-in plus uploaded."""
    kw = {}
    for n, (_, _, words) in PROPS.items():
        for w in words:
            kw.setdefault(w, []).append(n)
    for n, m in uploaded().items():
        for w in m.get("words", []):
            kw.setdefault(w, []).append(n)
    return kw


_img_cache = {}


def draw_image_prop(cv, name, x, y, u, hand=False):
    m = uploaded().get(name)
    if not m:
        return
    img = _img_cache.get(m["path"])
    if img is None:
        import numpy as np
        from PIL import Image
        img = skia.Image.fromarray(np.asarray(Image.open(m["path"]).convert("RGBA")).copy(),
                                   colorType=skia.kRGBA_8888_ColorType)
        _img_cache[m["path"]] = img
    h = m["size"] * u
    w = h * img.width() / img.height()
    top = y - (h * 0.5 if hand else h)
    cv.drawImageRect(img, skia.Rect.MakeXYWH(x - w / 2, top, w, h), skia.SamplingOptions(skia.FilterMode.kLinear))


def draw(cv, name, x, y, u, **kw):
    """Draw a floor/back prop with its floor point at (x, y); u = character height in pixels."""
    if name not in PROPS:
        return draw_image_prop(cv, name, x, y, u)
    cv.save()
    cv.translate(x, y)
    cv.scale(u * (-1 if kw.pop("flip", False) else 1), u)
    PROPS[name][1](cv, **kw)
    cv.restore()


def draw_front(cv, name, x, y, u, width, top, **kw):
    cv.save()
    cv.translate(x, y)
    cv.scale(u, u)
    PROPS[name][1](cv, width, top, **kw)
    cv.restore()


def draw_held(cv, name, H, ow):
    """Inside a character's drawing (units = that character), at hand point H."""
    cv.save()
    cv.translate(*H)
    if name in PROPS and PROPS[name][0] == "hand":
        PROPS[name][1](cv, ow)
    elif name in uploaded():
        draw_image_prop(cv, name, 0, 0, 1.0, hand=True)
    cv.restore()


def draw_worn(cv, name, where, ow, R=None, neck=None):
    if name not in PROPS:
        return
    layer, fn, _ = PROPS[name]
    if where == "neck" and name.startswith("necklace"):
        fn(cv, neck, ow)
    elif where == "head" and not name.startswith("necklace"):
        fn(cv, R, ow)
