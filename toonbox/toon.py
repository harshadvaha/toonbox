"""Draws a simple-style cartoon character from its saved settings, in any pose and expression.

Everything is drawn with vector shapes, so a character looks identical in every video and nothing can tear:
arms and legs are bendable tubes/lines, the face (eyes, brows, mouth) is drawn by the code.
Coordinates: origin at the feet, 1 unit = the character's height, y grows downward (screen style).
"""
import math
from dataclasses import dataclass, field

import skia

from . import props

INK = (28, 26, 34)

# --------------------------------------------------------------------------- character settings
BODY_STYLES = {"Blob": "blob", "Stick": "stick", "Simple clothes": "clothes"}
HEADS = ["Round", "Oval", "Wide", "Bean"]
HAIRS = ["None", "Short", "Spiky", "Long", "Bob", "Bun", "Ponytail", "Curly"]
EYES = ["Dots", "Big"]
BOTTOMS = ["Pants", "Skirt", "Shorts"]
EXTRAS = ["Glasses", "Moustache", "Beard", "Tie", "Hair bow", "Rosy cheeks"]

DEFAULT = {
    "name": "New character", "body": "Simple clothes", "head": "Round", "skin": "#F6D7B8", "hair": "Short",
    "hair_color": "#2B2220", "eyes": "Big", "top": "#FFFFFF", "bottom": "Pants", "bottom_color": "#2E3440",
    "extras": [], "height": 1.0, "width": 1.0, "head_size": 1.0,
}


def hexrgb(h):
    h = (h or "#888888").strip()
    if h.startswith("rgb"):
        nums = [float(x) for x in h[h.index("(") + 1:h.index(")")].split(",")[:3]]
        return tuple(int(round(v)) for v in nums)
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return (136, 136, 136)


def shade(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _paint(c, a=255):
    return skia.Paint(Color=skia.ColorSetARGB(a, *c), AntiAlias=True)


def _stroke(c, w, a=255):
    return skia.Paint(Color=skia.ColorSetARGB(a, *c), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                      StrokeWidth=w, StrokeCap=skia.Paint.kRound_Cap, StrokeJoin=skia.Paint.kRound_Join)


def _fill_out(cv, path, col, ow):
    cv.drawPath(path, _paint(col))
    cv.drawPath(path, _stroke(INK, ow))


def _oval(cx, cy, rx, ry):
    p = skia.Path()
    p.addOval(skia.Rect.MakeLTRB(cx - rx, cy - ry, cx + rx, cy + ry))
    return p


# --------------------------------------------------------------------------- expressions
#  brow: angle (+ = angry, inner end down), y (- = raised), asym (one brow higher)
#  eye: open, shape (n / happy / closed / wide), lid (top lid cover 0..1), lid_ang, pupil size, pupil_y
#  mouth: curve (-1 frown .. 1 smile), open (base opening), width, teeth, blush
EXPR = {
    "neutral":     dict(ba=0, by=0, bs=0, eo=1, es="n", lid=0, la=0, ps=1, py=0, mc=0.18, mo=0, mw=1, teeth=0, bl=0),
    "happy":       dict(ba=-6, by=-0.04, bs=0, eo=1, es="n", lid=0, la=0, ps=1, py=0, mc=0.85, mo=0, mw=1.15, teeth=0, bl=0),
    "laugh":       dict(ba=-8, by=-0.07, bs=0, eo=1, es="happy", lid=0, la=0, ps=1, py=0, mc=0.9, mo=0.6, mw=1.2, teeth=1, bl=0.3),
    "angry":       dict(ba=24, by=0.07, bs=0, eo=1, es="n", lid=0.32, la=20, ps=0.9, py=0, mc=-0.7, mo=0, mw=0.9, teeth=0, bl=0),
    "shocked":     dict(ba=-10, by=-0.16, bs=0, eo=1.25, es="wide", lid=0, la=0, ps=0.55, py=0, mc=-0.1, mo=0.5, mw=0.6, teeth=0, bl=0),
    "sad":         dict(ba=-20, by=-0.03, bs=0, eo=0.9, es="n", lid=0.25, la=-16, ps=1, py=0.08, mc=-0.65, mo=0, mw=0.8, teeth=0, bl=0),
    "tired":       dict(ba=0, by=0.03, bs=0, eo=0.85, es="n", lid=0.55, la=0, ps=1, py=0.05, mc=-0.25, mo=0, mw=0.7, teeth=0, bl=0),
    "unimpressed": dict(ba=2, by=0.06, bs=0, eo=1, es="n", lid=0.45, la=0, ps=1, py=0, mc=-0.05, mo=0, mw=0.75, teeth=0, bl=0),
    "smug":        dict(ba=8, by=-0.01, bs=0.1, eo=1, es="n", lid=0.4, la=4, ps=1, py=0, mc=0.6, mo=0, mw=0.9, teeth=0, bl=0),
    "suspicious":  dict(ba=16, by=0.05, bs=0.13, eo=0.9, es="n", lid=0.42, la=10, ps=0.9, py=0, mc=-0.3, mo=0, mw=0.7, teeth=0, bl=0),
    "confused":    dict(ba=-6, by=-0.06, bs=0.15, eo=1, es="n", lid=0, la=0, ps=1, py=-0.04, mc=-0.25, mo=0, mw=0.8, teeth=0, bl=0),
    "scared":      dict(ba=-18, by=-0.11, bs=0, eo=1.2, es="wide", lid=0, la=0, ps=0.55, py=0, mc=-0.5, mo=0.25, mw=1.0, teeth=1, bl=0),
    "love":        dict(ba=-6, by=-0.05, bs=0, eo=1, es="happy", lid=0, la=0, ps=1, py=0, mc=0.75, mo=0, mw=1, teeth=0, bl=1),
    "awkward":     dict(ba=-12, by=-0.04, bs=0.06, eo=1, es="n", lid=0, la=0, ps=0.9, py=0, mc=-0.1, mo=0.12, mw=1.15, teeth=1, bl=0.4),
    "thinking":    dict(ba=8, by=0, bs=0.13, eo=1, es="n", lid=0.18, la=0, ps=1, py=-0.12, mc=-0.1, mo=0, mw=0.6, teeth=0, bl=0),
}
EXPRESSIONS = list(EXPR)
NUMERIC = ["ba", "by", "bs", "eo", "lid", "la", "ps", "py", "mc", "mo", "mw", "bl"]

# Rhubarb mouth shapes -> (opening, width, teeth, tongue, round)
VISEME = {"X": (0.0, 1.0, 0, 0, 0), "A": (0.0, 0.85, 0, 0, 0), "B": (0.22, 1.0, 1, 0, 0), "C": (0.42, 1.0, 0, 0, 0),
          "D": (0.75, 1.1, 0, 1, 0), "E": (0.5, 0.72, 0, 0, 1), "F": (0.3, 0.45, 0, 0, 1), "G": (0.2, 0.9, 1, 0, 0),
          "H": (0.48, 0.92, 0, 1, 0)}


@dataclass
class Pose:
    lean: float = 0.0          # degrees, whole upper body around the hips
    tilt: float = 0.0          # degrees, head
    head_dy: float = 0.0       # head bob (units)
    look: float = 0.0          # -1 left .. 1 right
    squash: float = 1.0        # vertical squash/stretch
    hands: dict = field(default_factory=lambda: {"l": ("rel", 0.12, 0.985), "r": ("rel", 0.12, 0.985)})
    feet: dict = field(default_factory=lambda: {"l": (0.0, 0.0), "r": (0.0, 0.0)})
    face: dict = field(default_factory=lambda: dict(EXPR["neutral"]))
    eye_shape: str = "n"
    teeth: int = 0
    blink: float = 1.0         # 1 open, 0 closed
    mouth: str = "X"           # viseme letter
    holding: str = ""          # prop name held in one hand
    hold_side: str = "r"
    worn: list = field(default_factory=list)
    sit: float = 0.0           # 0 standing .. 1 seated


class Toon:
    def __init__(self, spec):
        self.spec = s = {**DEFAULT, **(spec or {})}
        self.style = BODY_STYLES.get(s["body"], "clothes")
        self.skin = hexrgb(s["skin"])
        self.hair_col = hexrgb(s["hair_color"])
        self.top = hexrgb(s["top"])
        self.bot = hexrgb(s["bottom_color"])
        self.extras = set(s.get("extras") or [])
        w = float(s.get("width", 1.0))
        hs = float(s.get("head_size", 1.0))
        self.ow = 0.011
        if self.style == "blob":
            self.R = 0.25 * w
            self.head_c = (0.0, -0.71)
            self.top_w, self.base_w = 0.52 * w, 0.66 * w
            self.shoulder = {"l": (-0.27 * w, -0.43), "r": (0.27 * w, -0.43)}
            self.arm = (0.17, 0.16)
            self.limb_w = 0.075
            self.hip = {"l": (-0.12 * w, -0.03), "r": (0.12 * w, -0.03)}
            self.leg = (0.02, 0.02)
            self.neck = (0.0, -0.4)
        else:
            self.R = 0.168 * hs
            self.head_c = (0.0, -(1.0 - self.R * 1.02))
            neck_y = self.head_c[1] + self.R * 0.93
            self.neck = (0.0, neck_y)
            sh_y = neck_y + 0.03
            self.hip_y = -0.37
            if self.style == "stick":
                self.shoulder = {"l": (0.0, sh_y + 0.02), "r": (0.0, sh_y + 0.02)}
                self.hip = {"l": (0.0, self.hip_y), "r": (0.0, self.hip_y)}
                self.limb_w = 0.024
                self.arm = (0.145, 0.145)
            else:
                self.shw = 0.088 * w
                self.hipw = 0.074 * w
                self.shoulder = {"l": (-self.shw + 0.018, sh_y + 0.012), "r": (self.shw - 0.018, sh_y + 0.012)}
                self.hip = {"l": (-0.042 * w, self.hip_y + 0.01), "r": (0.042 * w, self.hip_y + 0.01)}
                self.limb_w = 0.046
                self.arm = (0.14, 0.135)
            hh = -self.hip["l"][1]
            self.leg = (hh * 0.503, hh * 0.503)
        self.sh_y = self.shoulder["r"][1]

    # ------------------------------------------------------------------ geometry helpers
    @staticmethod
    def ik(S, T, a, b, side):
        dx, dy = T[0] - S[0], T[1] - S[1]
        d = math.hypot(dx, dy)
        d = min(max(d, abs(a - b) + 1e-4, 0.15 * (a + b)), (a + b) * 0.999)
        th = math.atan2(dy, dx)
        al = math.acos(max(-1, min(1, (a * a + d * d - b * b) / (2 * a * d))))
        best = None
        for sg in (1, -1):
            E = (S[0] + a * math.cos(th + sg * al), S[1] + a * math.sin(th + sg * al))
            score = side * E[0] + 0.35 * E[1]
            if best is None or score > best[0]:
                best = (score, E)
        E = best[1]
        H = (S[0] + d * math.cos(th), S[1] + d * math.sin(th))
        return E, H

    def hand_target(self, side_name, spec, head_center):
        sgn = -1 if side_name == "l" else 1
        S = self.shoulder[side_name]
        L = sum(self.arm)
        kind = spec[0]
        if kind == "abs":
            return (spec[1], spec[2])
        if kind == "face":
            return (head_center[0] + sgn * spec[1] * self.R, head_center[1] + spec[2] * self.R)
        return (S[0] + sgn * spec[1] * L, S[1] + spec[2] * L)

    # ------------------------------------------------------------------ drawing
    def draw(self, cv, x, y, scale, pose: Pose, flip=False):
        cv.save()
        cv.translate(x, y)
        cv.scale(scale * (-1 if flip else 1), scale * pose.squash)
        if self.style == "blob":
            self._draw_blob(cv, pose)
        else:
            self._draw_person(cv, pose)
        cv.restore()

    def _rot(self, p, c, deg):
        a = math.radians(deg)
        dx, dy = p[0] - c[0], p[1] - c[1]
        return (c[0] + dx * math.cos(a) - dy * math.sin(a), c[1] + dx * math.sin(a) + dy * math.cos(a))

    def _tube(self, cv, pts, col, w, outline=True):
        path = skia.Path()
        path.moveTo(*pts[0])
        if len(pts) == 3:
            # smooth bend through the elbow
            c = (2 * pts[1][0] - (pts[0][0] + pts[2][0]) / 2, 2 * pts[1][1] - (pts[0][1] + pts[2][1]) / 2)
            mid = ((pts[0][0] + c[0]) / 2, (pts[0][1] + c[1]) / 2)
            path.lineTo(*mid)
            path.quadTo(c[0], c[1], (c[0] + pts[2][0]) / 2, (c[1] + pts[2][1]) / 2)
            path.lineTo(*pts[2])
        else:
            for p in pts[1:]:
                path.lineTo(*p)
        if outline:
            cv.drawPath(path, _stroke(INK, w + 2 * self.ow))
        cv.drawPath(path, _stroke(col, w))

    def _limbs(self, pose, hipc, lean, head_center):
        """Returns arm (S, E, H) per side and leg (Hp, K, F) per side, in body units."""
        arms = {}
        for sd in ("l", "r"):
            sgn = -1 if sd == "l" else 1
            S0 = self.shoulder[sd]
            spec = pose.hands.get(sd) or ("rel", 0.12, 0.985)
            T0 = self.hand_target(sd, spec, head_center if spec[0] == "face" else (0, 0))
            S = self._rot(S0, hipc, lean)
            T = T0 if spec[0] == "face" else self._rot(T0, hipc, lean)
            E, H = self.ik(S, T, self.arm[0], self.arm[1], sgn)
            arms[sd] = (S, E, H)
        legs = {}
        off = pose.sit * 0.17 if self.style != "blob" else 0.0
        for sd in ("l", "r"):
            sgn = -1 if sd == "l" else 1
            Hp = (self.hip[sd][0], self.hip[sd][1] + off)
            fx, lift = pose.feet.get(sd, (0, 0))
            F = (Hp[0] + sgn * (0.035 + 0.05 * pose.sit) + fx, -lift)
            if self.style == "blob":
                legs[sd] = (Hp, Hp, F)
                continue
            K, F2 = self.ik(Hp, F, self.leg[0], self.leg[1], sgn * (0.4 + 3 * pose.sit))
            legs[sd] = (Hp, K, F2)
        return arms, legs

    def _draw_person(self, cv, pose):
        hipc = (0.0, self.hip_y)
        lean = pose.lean
        neck = self._rot(self.neck, hipc, lean)
        hc0 = self._rot(self.head_c, hipc, lean)
        hc = (hc0[0], hc0[1] + pose.head_dy)
        arms, legs = self._limbs(pose, hipc, lean, hc)
        ow = self.ow
        # legs
        for sd in ("l", "r"):
            Hp, K, F = legs[sd]
            if self.style == "stick":
                self._tube(cv, [Hp, K, F], INK, self.limb_w, outline=False)
            else:
                self._tube(cv, [Hp, K, F], self.bot if self.spec["bottom"] != "Skirt" else self.skin, 0.05)
                shoe = _oval(F[0] + (-0.012 if sd == "l" else 0.012), F[1] - 0.006, 0.038, 0.02)
                _fill_out(cv, shoe, (40, 40, 48), ow)
        if self.style == "clothes" and self.spec["bottom"] == "Shorts":
            for sd in ("l", "r"):
                Hp, K, F = legs[sd]
                m = (Hp[0] * 0.45 + K[0] * 0.55, Hp[1] * 0.45 + K[1] * 0.55)
                self._tube(cv, [Hp, m], self.bot, 0.058)
        off = pose.sit * 0.17
        cv.save()
        cv.translate(0, off)
        # hair behind the head
        cv.save()
        cv.translate(*hc)
        cv.rotate(pose.tilt)
        self._hair(cv, back=True)
        cv.restore()
        # torso
        if self.style == "stick":
            hip_pt = self._rot(hipc, hipc, lean)
            self._tube(cv, [neck, hip_pt], INK, self.limb_w, outline=False)
        else:
            self._torso(cv, hipc, lean, legs)
        # head + face
        cv.save()
        cv.translate(*hc)
        cv.rotate(pose.tilt)
        head = self._head_path()
        if self.style == "clothes":
            nk = skia.Path()
            nk.addRect(skia.Rect.MakeLTRB(-0.022, self.R * 0.6, 0.022, self.R * 1.25))
            _fill_out(cv, nk, self.skin, ow)
        _fill_out(cv, head, self.skin, ow * 1.15)
        self._face(cv, pose)
        self._hair(cv, back=False)
        for w in pose.worn:
            props.draw_worn(cv, w, "head", self.ow, R=self.R)
        cv.restore()
        for w in pose.worn:
            props.draw_worn(cv, w, "neck", self.ow, neck=(neck[0], neck[1] + 0.035))
        # arms on top (so hands can reach the face)
        for sd in ("l", "r"):
            S, E, H = arms[sd]
            if self.style == "stick":
                self._tube(cv, [S, E, H], INK, self.limb_w, outline=False)
            else:
                self._tube(cv, [S, E, H], self.top, self.limb_w)
                hp = _oval(H[0], H[1], 0.03, 0.03)
                _fill_out(cv, hp, self.skin, ow)
            if pose.holding and sd == pose.hold_side:
                props.draw_held(cv, pose.holding, H, self.ow)
        cv.restore()

    def _torso(self, cv, hipc, lean, legs):
        ow = self.ow
        sh_y = self.neck[1] + 0.012
        hy = self.hip_y + 0.02
        p = skia.Path()
        pts = [(-self.shw, sh_y + 0.02), (-self.shw + 0.02, sh_y), (self.shw - 0.02, sh_y), (self.shw, sh_y + 0.02),
               (self.hipw, hy), (-self.hipw, hy)]
        pts = [self._rot(q, hipc, lean) for q in pts]
        p.moveTo(*pts[0])
        p.quadTo(pts[1][0], pts[1][1] - 0.004, pts[1][0] + 0.01, pts[1][1])
        p.lineTo(*pts[2])
        p.quadTo(pts[3][0], pts[3][1] - 0.02, pts[3][0], pts[3][1])
        p.lineTo(*pts[4])
        p.lineTo(*pts[5])
        p.close()
        _fill_out(cv, p, self.top, ow)
        if self.spec["bottom"] == "Skirt":
            sk = skia.Path()
            a = [(-self.hipw - 0.004, hy - 0.02), (self.hipw + 0.004, hy - 0.02), (self.hipw + 0.05, hy + 0.13),
                 (-self.hipw - 0.05, hy + 0.13)]
            a = [self._rot(q, hipc, lean) if i < 2 else q for i, q in enumerate(a)]
            sk.moveTo(*a[0])
            for q in a[1:]:
                sk.lineTo(*q)
            sk.close()
            _fill_out(cv, sk, self.bot, ow)
        else:
            belt = skia.Path()
            a = [(-self.hipw, hy - 0.03), (self.hipw, hy - 0.03), (self.hipw + 0.002, hy + 0.005),
                 (-self.hipw - 0.002, hy + 0.005)]
            a = [self._rot(q, hipc, lean) for q in a]
            belt.moveTo(*a[0])
            for q in a[1:]:
                belt.lineTo(*q)
            belt.close()
            _fill_out(cv, belt, self.bot, ow)
        # collar
        c = [self._rot(q, hipc, lean) for q in [(-0.028, sh_y - 0.002), (0.0, sh_y + 0.03), (0.028, sh_y - 0.002)]]
        col = skia.Path()
        col.moveTo(*c[0])
        col.lineTo(*c[1])
        col.lineTo(*c[2])
        cv.drawPath(col, _stroke(INK, ow))
        if "Tie" in self.extras:
            t = [self._rot(q, hipc, lean) for q in [(-0.012, sh_y + 0.01), (0.012, sh_y + 0.01), (0.016, sh_y + 0.1),
                                                     (0.0, sh_y + 0.125), (-0.016, sh_y + 0.1)]]
            tp = skia.Path()
            tp.moveTo(*t[0])
            for q in t[1:]:
                tp.lineTo(*q)
            tp.close()
            _fill_out(cv, tp, (214, 40, 40), ow * 0.9)

    def _head_path(self):
        R = self.R
        shape = self.spec["head"]
        if shape == "Oval":
            return _oval(0, 0, R * 0.86, R * 1.06)
        if shape == "Wide":
            return _oval(0, 0, R * 1.18, R * 0.9)
        if shape == "Bean":
            p = skia.Path()
            p.moveTo(-R * 1.08, 0)
            p.cubicTo(-R * 1.12, -R * 1.15, R * 1.12, -R * 1.15, R * 1.08, -R * 0.05)
            p.cubicTo(R * 1.02, R * 0.85, R * 0.3, R * 0.95, -R * 0.2, R * 0.92)
            p.cubicTo(-R * 0.8, R * 0.9, -R * 1.05, R * 0.6, -R * 1.08, 0)
            p.close()
            return p
        return _oval(0, 0, R, R * 0.97)

    def _phone(self, cv, H):
        p = skia.Path()
        p.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(H[0] - 0.018, H[1] - 0.05, H[0] + 0.018, H[1] + 0.01),
                                         0.008, 0.008))
        _fill_out(cv, p, (245, 245, 250), self.ow * 0.8)

    # ------------------------------------------------------------------ blob body (one shape, face on top part)
    def _blob_path(self, lean_px):
        tw, bw = self.top_w, self.base_w
        p = skia.Path()
        p.moveTo(-bw / 2, 0)
        p.cubicTo(-bw / 2 - 0.01, -0.35, -tw / 2 + lean_px * 0.5, -0.6, -tw / 2 + lean_px * 0.8, -0.74)
        p.cubicTo(-tw / 2 + lean_px, -1.05, tw / 2 + lean_px, -1.05, tw / 2 + lean_px * 0.8, -0.74)
        p.cubicTo(tw / 2 + lean_px * 0.5, -0.6, bw / 2 + 0.01, -0.35, bw / 2, 0)
        p.quadTo(0, 0.02, -bw / 2, 0)
        p.close()
        return p

    def _draw_blob(self, cv, pose):
        ow = self.ow * 1.2
        shift = math.sin(math.radians(pose.lean + pose.tilt * 0.6)) * 0.9
        hc = (self.head_c[0] + shift * 0.75, self.head_c[1] + pose.head_dy * 0.6)
        arms, legs = self._limbs(pose, (0, 0), 0, hc)
        for sd in ("l", "r"):
            F = legs[sd][2]
            _fill_out(cv, _oval(F[0], F[1] - 0.012, 0.06, 0.028), shade(self.skin, 0.9), ow)
        body = self._blob_path(shift)
        _fill_out(cv, body, self.skin, ow)
        if self.spec["bottom"] != "Pants" or self.spec.get("blob_outfit"):
            pass
        cv.save()
        cv.translate(*hc)
        cv.rotate(pose.tilt * 0.35)
        self._face(cv, pose)
        self._hair(cv, back=False, blob=True)
        cv.restore()
        for sd in ("l", "r"):
            S, E, H = arms[sd]
            sgn = -1 if sd == "l" else 1
            S = (S[0] + shift * 0.35 - sgn * 0.02, S[1])
            self._tube(cv, [S, E, H], self.skin, self.limb_w)
            if pose.holding and sd == pose.hold_side:
                props.draw_held(cv, pose.holding, H, self.ow)
        # hide the arm outline where it joins the body
        for sd in ("l", "r"):
            S = arms[sd][0]
            sgn = -1 if sd == "l" else 1
            cv.drawCircle(S[0] + shift * 0.35 - sgn * 0.02, S[1], self.limb_w * 0.5, _paint(self.skin))

    # ------------------------------------------------------------------ face
    def _face(self, cv, pose):
        f = pose.face
        R = self.R
        big = self.spec["eyes"] == "Big"
        lk = max(-1.0, min(1.0, pose.look))
        fx = lk * 0.14 * R
        cv.save()
        cv.translate(fx, 0)
        ex, ey = 0.36 * R, -0.06 * R
        ow = self.ow
        # cheeks
        if f["bl"] > 0.05 or "Rosy cheeks" in self.extras:
            a = int(110 * max(f["bl"], 0.6 if "Rosy cheeks" in self.extras else 0))
            for sg in (-1, 1):
                cv.drawOval(skia.Rect.MakeLTRB(sg * 0.58 * R - 0.13 * R, 0.2 * R - 0.07 * R, sg * 0.58 * R + 0.13 * R,
                                               0.2 * R + 0.07 * R), _paint((240, 110, 120), a))
        # eyes
        open_ = max(0.0, f["eo"] * pose.blink)
        for sg in (-1, 1):
            cx = sg * ex
            self._eye(cv, cx, ey, sg, open_, pose.eye_shape, f, big, lk, ow)
        # brows
        for sg in (-1, 1):
            bx = sg * ex
            by = ey - (0.42 if big else 0.3) * R + f["by"] * R - (f["bs"] * R if sg == 1 else 0)
            ang = math.radians(f["ba"]) * sg
            L = 0.2 * R
            x0, y0 = bx - sg * L * math.cos(ang) * -1, by
            p = skia.Path()
            ix, iy = bx - sg * L * math.cos(ang), by + L * math.sin(abs(ang)) * (1 if f["ba"] > 0 else -1)
            ox, oy = bx + sg * L * math.cos(ang), by - L * math.sin(abs(ang)) * (1 if f["ba"] > 0 else -1)
            p.moveTo(ix, iy)
            p.quadTo(bx, by - 0.04 * R, ox, oy)
            cv.drawPath(p, _stroke(INK, max(ow * 1.3, 0.05 * R)))
        # nose for wide heads / moustache / beard
        if "Moustache" in self.extras:
            m = skia.Path()
            my = 0.3 * R
            m.moveTo(-0.3 * R, my + 0.08 * R)
            m.quadTo(-0.15 * R, my - 0.1 * R, 0, my - 0.02 * R)
            m.quadTo(0.15 * R, my - 0.1 * R, 0.3 * R, my + 0.08 * R)
            cv.drawPath(m, _stroke(INK, 0.06 * R))
        self._mouth(cv, pose, R, ow)
        if "Beard" in self.extras:
            b = skia.Path()
            b.moveTo(-0.85 * R, 0.25 * R)
            b.quadTo(-0.7 * R, 1.15 * R, 0, 1.1 * R)
            b.quadTo(0.7 * R, 1.15 * R, 0.85 * R, 0.25 * R)
            b.quadTo(0.4 * R, 0.85 * R, 0, 0.82 * R)
            b.quadTo(-0.4 * R, 0.85 * R, -0.85 * R, 0.25 * R)
            b.close()
            _fill_out(cv, b, self.hair_col, ow)
        if "Glasses" in self.extras:
            gr = 0.24 * R if big else 0.2 * R
            for sg in (-1, 1):
                cv.drawCircle(sg * ex, ey, gr, _stroke(INK, ow * 1.2))
            cv.drawLine(-ex + gr, ey, ex - gr, ey, _stroke(INK, ow * 1.2))
        cv.restore()

    def _eye(self, cv, cx, cy, sg, open_, shape, f, big, lk, ow):
        R = self.R
        rx, ry = (0.2 * R, 0.24 * R) if big else (0.075 * R, 0.1 * R)
        if shape == "wide":
            rx, ry = (rx * 1.15, ry * 1.15) if big else (rx * 1.35, ry * 1.35)
        if shape == "happy":
            p = skia.Path()
            p.moveTo(cx - rx * 1.1, cy + ry * 0.35)
            p.quadTo(cx, cy - ry * 1.3, cx + rx * 1.1, cy + ry * 0.35)
            cv.drawPath(p, _stroke(INK, max(ow * 1.3, 0.055 * R)))
            return
        if shape == "closed" or open_ < 0.12:
            p = skia.Path()
            p.moveTo(cx - rx, cy)
            p.quadTo(cx, cy + ry * 0.45, cx + rx, cy)
            cv.drawPath(p, _stroke(INK, max(ow * 1.2, 0.05 * R)))
            return
        ryo = ry * min(1.3, open_)
        if big:
            eye = _oval(cx, cy, rx, ryo)
            cv.drawPath(eye, _paint((255, 255, 255)))
            cv.save()
            cv.clipPath(eye, doAntiAlias=True)
            pr = 0.095 * R * f["ps"]
            px = cx + lk * rx * 0.45
            py = cy + f["py"] * R + ry * 0.12
            cv.drawCircle(px, py, pr, _paint(INK))
            cv.drawCircle(px + pr * 0.35, py - pr * 0.4, pr * 0.3, _paint((255, 255, 255)))
            self._lid(cv, cx, cy, rx, ryo, sg, f)
            cv.restore()
            cv.drawPath(eye, _stroke(INK, ow * 1.1))
        else:
            dot = _oval(cx + lk * 0.03 * R, cy + f["py"] * R * 0.5, rx, ryo)
            cv.drawPath(dot, _paint(INK))
            if f["lid"] > 0.05:
                cv.save()
                cv.clipPath(_oval(cx, cy, rx * 2.2, ry * 2.2), doAntiAlias=True)
                self._lid(cv, cx, cy, rx * 1.6, ryo * 1.2, sg, f, line=True)
                cv.restore()

    def _lid(self, cv, cx, cy, rx, ry, sg, f, line=True):
        lid = f["lid"]
        if lid < 0.04:
            return
        edge = cy - ry + 2 * ry * lid
        a = math.radians(f["la"]) * sg
        dy = math.tan(a) * rx
        p = skia.Path()
        p.moveTo(cx - rx * 1.5, cy - ry * 2)
        p.lineTo(cx + rx * 1.5, cy - ry * 2)
        p.lineTo(cx + rx * 1.5, edge - dy * 1.5 * -1 if sg < 0 else edge - dy * 1.5)
        p.lineTo(cx - rx * 1.5, edge + dy * 1.5 * -1 if sg < 0 else edge + dy * 1.5)
        p.close()
        cv.drawPath(p, _paint(self.skin))
        if line:
            y1 = edge - dy * 1.5 * -1 if sg < 0 else edge - dy * 1.5
            y0 = edge + dy * 1.5 * -1 if sg < 0 else edge + dy * 1.5
            cv.drawLine(cx - rx * 1.5, y0, cx + rx * 1.5, y1, _stroke(INK, self.ow * 1.3))

    def _mouth(self, cv, pose, R, ow):
        f = pose.face
        o, w, teeth, tongue, rnd = VISEME.get(pose.mouth, VISEME["X"])
        talking = pose.mouth not in ("X",)
        opening = max(o, f["mo"]) if not talking else max(o, f["mo"] * 0.6)
        if pose.mouth == "A":
            opening = 0.0
        width = 0.3 * R * (w if talking else 1.0) * f["mw"]
        if rnd:
            width = 0.3 * R * w
        cy = (0.62 if "Moustache" in self.extras else 0.46) * R
        curve = f["mc"]
        if opening < 0.05:
            p = skia.Path()
            p.moveTo(-width, cy - curve * 0.1 * R)
            p.quadTo(0, cy + curve * 0.14 * R, width, cy - curve * 0.1 * R)
            cv.drawPath(p, _stroke(INK, max(ow * 1.2, 0.05 * R)))
            return
        h = opening * 0.4 * R
        top = cy - curve * 0.08 * R - h * 0.25
        corner = cy - curve * 0.1 * R
        p = skia.Path()
        p.moveTo(-width, corner)
        p.quadTo(0, top - (h * 0.15 if rnd else -curve * 0.04 * R), width, corner)
        p.quadTo(width * 0.9 if rnd else width * 0.7, corner + h * (1.0 + max(0, curve) * 0.4),
                 0, corner + h * (1.05 + max(0, curve) * 0.3))
        p.quadTo(-(width * 0.9 if rnd else width * 0.7), corner + h * (1.0 + max(0, curve) * 0.4), -width, corner)
        p.close()
        cv.drawPath(p, _paint((92, 28, 40)))
        cv.save()
        cv.clipPath(p, doAntiAlias=True)
        if teeth or (pose.teeth and opening > 0.08):
            cv.drawRect(skia.Rect.MakeLTRB(-width, top - h, width, top + h * 0.32), _paint((255, 255, 255)))
        if tongue or opening > 0.55:
            cv.drawOval(skia.Rect.MakeLTRB(-width * 0.6, corner + h * 0.6, width * 0.6, corner + h * 1.6),
                        _paint((232, 106, 118)))
        cv.restore()
        cv.drawPath(p, _stroke(INK, ow * 1.1))

    # ------------------------------------------------------------------ hair
    def _hair(self, cv, back, blob=False):
        style = self.spec["hair"]
        if style == "None":
            if "Hair bow" in self.extras and not back:
                self._bow(cv)
            return
        R = self.R
        col = self.hair_col
        ow = self.ow
        if blob:
            R = self.R * 1.05
            cv.translate(0, -0.06)
        if back:
            if style == "Long":
                p = skia.Path()
                p.moveTo(-R * 1.05, -R * 0.2)
                p.cubicTo(-R * 1.25, R * 1.2, -R * 1.1, R * 2.0, -R * 0.9, R * 2.1)
                p.lineTo(R * 0.9, R * 2.1)
                p.cubicTo(R * 1.1, R * 2.0, R * 1.25, R * 1.2, R * 1.05, -R * 0.2)
                p.close()
                _fill_out(cv, p, col, ow)
            elif style == "Bob":
                p = skia.Path()
                p.moveTo(-R * 1.1, -R * 0.2)
                p.cubicTo(-R * 1.25, R * 0.6, -R * 1.2, R * 1.0, -R * 0.85, R * 1.05)
                p.lineTo(R * 0.85, R * 1.05)
                p.cubicTo(R * 1.2, R * 1.0, R * 1.25, R * 0.6, R * 1.1, -R * 0.2)
                p.close()
                _fill_out(cv, p, col, ow)
            elif style == "Ponytail":
                p = skia.Path()
                p.moveTo(R * 0.75, -R * 0.55)
                p.cubicTo(R * 1.6, -R * 0.6, R * 1.7, R * 0.5, R * 1.35, R * 1.1)
                p.cubicTo(R * 1.25, R * 0.5, R * 1.1, R * 0.0, R * 0.8, -R * 0.1)
                p.close()
                _fill_out(cv, p, col, ow)
            elif style == "Bun":
                _fill_out(cv, _oval(0, -R * 1.05, R * 0.42, R * 0.36), col, ow)
            return
        # front / top part
        head = self._head_path()
        if style == "Spiky":
            n = 6
            for i in range(n):
                a0 = math.pi * (1.08 + 0.84 * i / n)
                a1 = math.pi * (1.08 + 0.84 * (i + 1) / n)
                am = (a0 + a1) / 2
                p = skia.Path()
                p.moveTo(math.cos(a0) * R * 0.9, math.sin(a0) * R * 0.9)
                p.lineTo(math.cos(am) * R * 1.42, math.sin(am) * R * 1.38)
                p.lineTo(math.cos(a1) * R * 0.9, math.sin(a1) * R * 0.9)
                p.close()
                _fill_out(cv, p, col, ow)
            style = "Short"
        if style == "Curly":
            for i in range(9):
                a = math.pi * (1.0 + i / 8)
                x, y = math.cos(a) * R * 0.95, math.sin(a) * R * 0.92
                _fill_out(cv, _oval(x, y, R * 0.3, R * 0.27), col, ow)
            cap = skia.Path()
            cap.addOval(skia.Rect.MakeLTRB(-R * 0.95, -R * 1.1, R * 0.95, -R * 0.3))
            cv.drawPath(cap, _paint(col))
        else:
            cv.save()
            cv.clipPath(head, doAntiAlias=True)
            cap = skia.Path()
            if style in ("Bob", "Long", "Ponytail", "Bun"):
                cap.moveTo(-R * 1.3, -R * 0.0)
                cap.quadTo(-R * 1.0, -R * 1.5, R * 0.2, -R * 1.3)
                cap.quadTo(R * 1.3, -R * 1.1, R * 1.3, R * 0.05)
                cap.quadTo(R * 0.8, -R * 0.55, R * 0.05, -R * 0.62)
                cap.quadTo(-R * 0.6, -R * 0.55, -R * 1.3, R * 0.0)
            else:  # Short
                cap.moveTo(-R * 1.3, -R * 0.15)
                cap.quadTo(-R * 1.0, -R * 1.5, R * 0.1, -R * 1.25)
                cap.quadTo(R * 1.3, -R * 1.1, R * 1.3, -R * 0.15)
                cap.quadTo(R * 0.9, -R * 0.62, R * 0.25, -R * 0.68)
                cap.quadTo(-R * 0.5, -R * 0.75, -R * 1.3, -R * 0.15)
            cap.close()
            cv.drawPath(cap, _paint(col))
            cv.drawPath(cap, _stroke(INK, ow))
            cv.restore()
            cv.drawPath(head, _stroke(INK, ow * 1.15))
        if "Hair bow" in self.extras:
            self._bow(cv)

    def _bow(self, cv):
        R = self.R
        x, y = R * 0.55, -R * 0.85
        col = (236, 72, 120)
        for sg in (-1, 1):
            p = skia.Path()
            p.moveTo(x, y)
            p.lineTo(x + sg * R * 0.32, y - R * 0.18)
            p.lineTo(x + sg * R * 0.32, y + R * 0.18)
            p.close()
            _fill_out(cv, p, col, self.ow)
        _fill_out(cv, _oval(x, y, R * 0.08, R * 0.08), col, self.ow)

    # ------------------------------------------------------------------ geometry used by the stage
    def head_top(self):
        return -1.0 if self.style != "blob" else -1.0

    def head_center(self):
        return self.head_c


def set_expression(pose, name, blend=1.0):
    e = EXPR.get(name, EXPR["neutral"])
    pose.face = {k: e[k] for k in NUMERIC}
    pose.eye_shape = e["es"]
    pose.teeth = e["teeth"]
    return pose


def sheet(spec, names=("neutral", "happy", "angry", "shocked", "sad", "unimpressed"), cell=360):
    """Preview picture: the character with a few expressions side by side."""
    t = Toon(spec)
    cols = 3
    rows = (len(names) + cols - 1) // cols
    W, H = cell * cols, int(cell * 1.25) * rows
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    cv = surf.getCanvas()
    cv.clear(skia.ColorSetARGB(255, 238, 241, 245))
    font = _font(cell * 0.075)
    for i, n in enumerate(names):
        cx = (i % cols) * cell + cell / 2
        by = (i // cols) * int(cell * 1.25)
        pose = set_expression(Pose(), n)
        if n == "happy":
            pose.hands = {"l": ("rel", 0.18, 0.95), "r": ("rel", 0.55, -0.7)}
        elif n == "angry":
            pose.hands = {"l": ("rel", 0.05, 0.75), "r": ("rel", 0.05, 0.75)}
        elif n == "shocked":
            pose.hands = {"l": ("rel", 0.55, -0.7), "r": ("rel", 0.55, -0.7)}
            pose.mouth = "X"
        elif n == "sad":
            pose.lean, pose.head_dy = 0, 0.01
        elif n == "unimpressed":
            pose.hands = {"l": ("rel", -0.55, 0.42), "r": ("rel", -0.55, 0.42)}
        h = cell * 0.98 * float(t.spec.get("height", 1.0)) / 1.1
        t.draw(cv, cx, by + cell * 1.1, h, pose)
        p = _paint((70, 76, 90))
        tw = font.measureText(n)
        cv.drawString(n, cx - tw / 2, by + cell * 1.2, font, p)
    img = surf.makeImageSnapshot().toarray()
    from PIL import Image
    return Image.fromarray(img[..., :3].copy())


_fonts = {}


def _font(size, bold=True):
    key = (round(size), bold)
    if key in _fonts:
        return _fonts[key]
    tf = None
    for path in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/Library/Fonts/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            tf = skia.Typeface.MakeFromFile(path)
            if tf:
                break
        except Exception:
            continue
    f = skia.Font(tf or skia.Typeface(), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    _fonts[key] = f
    return f
