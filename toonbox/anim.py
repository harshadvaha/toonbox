"""Turns the storyboard into a pose for every character on every frame.

Motion uses springs, so gestures overshoot a little and settle (follow-through); characters breathe, sway,
blink, glance at whoever is talking, and their hands beat along with the loudness of their own voice.
"""
import math
import random

import numpy as np

from .toon import EXPR, NUMERIC, Pose

# near = the arm on the side of the person being talked to, far = the other arm
GEST = {
    "none": {},
    "talk": {"n": ("rel", 0.32, 0.5), "beat": True},
    "point": {"n": ("rel", 1.0, -0.04)},
    "open_palm": {"n": ("rel", 0.72, 0.4)},
    "shrug": {"n": ("rel", 0.62, 0.38), "f": ("rel", 0.62, 0.38)},
    "hands_up": {"n": ("rel", 0.6, -0.72), "f": ("rel", 0.6, -0.72)},
    "cheer": {"n": ("rel", 0.35, -0.95), "f": ("rel", 0.35, -0.95), "osc": ("both", 0.0, 0.05, 4.0)},
    "calm": {"n": ("rel", 0.55, 0.18), "f": ("rel", 0.55, 0.18), "osc": ("both", 0.0, 0.05, 2.2)},
    "cross_arms": {"n": ("rel", -0.55, 0.42), "f": ("rel", -0.5, 0.38)},
    "hips": {"n": ("rel", 0.06, 0.72), "f": ("rel", 0.06, 0.72)},
    "self": {"n": ("rel", -0.38, 0.32)},
    "clasp": {"n": ("rel", -0.3, 0.55), "f": ("rel", -0.3, 0.55)},
    "facepalm": {"n": ("face", 0.15, -0.05)},
    "chin": {"n": ("face", 0.2, 1.05)},
    "wave": {"n": ("rel", 0.65, -0.7), "osc": ("n", 0.13, 0.0, 4.5)},
    "beckon": {"n": ("rel", 0.75, 0.12), "osc": ("n", 0.0, 0.1, 3.0)},
    "fists": {"n": ("rel", 0.3, 0.5), "f": ("rel", 0.3, 0.5), "osc": ("both", 0.0, 0.035, 7.0)},
    "head_hold": {"n": ("face", 1.15, -0.3), "f": ("face", 1.15, -0.3)},
    "cover_mouth": {"n": ("face", 0.1, 0.55)},
    "phone": {"f": ("face", 1.15, 0.05)},
}
REST = ("rel", 0.12, 0.985)
HOLD = ("rel", 0.28, 0.55)


def _bump(p):
    return math.sin(math.pi * min(1, max(0, p)))


class Spring:
    def __init__(self, x, w, z):
        self.x = np.array(x, float)
        self.v = np.zeros_like(self.x)
        self.w, self.z = w, z

    def step(self, target, dt):
        a = self.w * self.w * (np.asarray(target, float) - self.x) - 2 * self.z * self.w * self.v
        self.v += a * dt
        self.x += self.v * dt
        return self.x


class Actor:
    def __init__(self, name, toon, x, h, fps, seed):
        self.name, self.toon, self.x, self.h = name, toon, x, h
        self.rnd = random.Random(seed)
        self.phase = self.rnd.random() * 10
        rest = self._abs("l", REST, 0) + self._abs("r", REST, 0)
        self.hand_s = Spring(rest, 13.0, 0.55)
        self.face_s = Spring([EXPR["neutral"][k] for k in NUMERIC], 20.0, 0.85)
        self.body_s = Spring([0, 0, 0, 0, 1.0], 9.0, 0.6)  # lean, tilt, head_dy, look, squash
        self.blinks = self._blinks(fps)
        self.toward = 1

    def _blinks(self, fps):
        out, t = [], self.rnd.uniform(0.5, 2.5)
        while t < 3600:
            out.append(t)
            if self.rnd.random() < 0.15:
                out.append(t + 0.28)  # double blink
            t += self.rnd.uniform(2.0, 5.0)
        return np.array(out)

    def _abs(self, side, spec, head_dy):
        tn = self.toon
        if spec[0] == "face":
            hc = (tn.head_c[0], tn.head_c[1] + head_dy)
            sgn = -1 if side == "l" else 1
            return [hc[0] + sgn * spec[1] * tn.R, hc[1] + spec[2] * tn.R]
        return list(tn.hand_target(side, spec, (0, 0)))

    def blink_at(self, t):
        i = np.searchsorted(self.blinks, t)
        best = 1.0
        for j in (i - 1, i):
            if 0 <= j < len(self.blinks):
                d = abs(t - self.blinks[j])
                if d < 0.09:
                    best = min(best, d / 0.09)
        return best


def _active(acts, key, t):
    """Latest-started act of this kind that covers time t."""
    cur = None
    for a in acts:
        if key in a and a["t0"] <= t < a["t1"]:
            if cur is None or a["t0"] >= cur["t0"]:
                cur = a
    return cur


class Animator:
    def __init__(self, actors, plan, lines, mouth, env, fps):
        self.A = {a.name: a for a in actors}
        self.plan, self.lines, self.mouth, self.env, self.fps = plan, lines, mouth, env, fps
        self.acts = {n: [a for a in plan["acts"] if a["char"] == n] for n in self.A}
        xs = {a.name: a.x for a in actors}
        for a in actors:
            others = [xs[o] for o in xs if o != a.name]
            a.toward = 1 if not others or (sum(others) / len(others)) >= a.x else -1

    def speaker_at(self, t):
        for l in self.lines:
            if l["start"] - 0.03 <= t <= l["end"] + 0.05:
                return l["speaker"]
        return None

    def scene_at(self, t):
        sc = self.plan["scenes"][0]
        for s in self.plan["scenes"]:
            if s["start"] <= t:
                sc = s
        return sc

    def step(self, fi):
        t = fi / self.fps
        dt = 1.0 / self.fps
        speaker = self.speaker_at(t)
        env = float(self.env[min(fi, len(self.env) - 1)]) if len(self.env) else 0.0
        scene = self.scene_at(t)
        out = {}
        for n, a in self.A.items():
            acts = self.acts[n]
            pose = Pose()
            talking = speaker == n
            # ---- expression
            ea = _active(acts, "expr", t)
            ename = ea["expr"] if ea and (t - ea["t1"] < 0) else "neutral"
            if ea is None:
                ename = "neutral"
            e = EXPR.get(ename, EXPR["neutral"])
            face = a.face_s.step([e[k] for k in NUMERIC], dt)
            pose.face = dict(zip(NUMERIC, face))
            pose.eye_shape, pose.teeth = e["es"], e["teeth"]
            # ---- body targets
            lean = 1.2 * math.sin(t * 2 * math.pi / 5.5 + a.phase)
            tilt = 0.0
            head_dy = 0.0
            look = 0.0
            squash = 1 + 0.006 * math.sin(t * 2 * math.pi / 3.2 + a.phase)
            y_off = 0.0
            if speaker and speaker != n and speaker in self.A:
                look = 0.75 * (1 if self.A[speaker].x > a.x else -1)
                lean += 2.0 * (1 if self.A[speaker].x > a.x else -1)
            elif talking:
                glance = (math.sin(t * 0.9 + a.phase) > 0.75)
                look = 0.0 if glance else 0.6 * a.toward
                head_dy -= 0.006 * env
                tilt += 3.0 * math.sin(t * 2.3 + a.phase) * min(1, env * 1.5)
            if ename in ("confused", "suspicious", "thinking"):
                tilt += 7 * a.toward
            if ename == "sad":
                head_dy += 0.012
            ba = _active(acts, "body", t)
            if ba:
                p = (t - ba["t0"]) / max(0.05, ba["t1"] - ba["t0"])
                k = ba["body"]
                if k == "nod":
                    head_dy += 0.014 * max(0, math.sin(2 * math.pi * 2 * p))
                elif k == "shake":
                    look += 0.55 * math.sin(2 * math.pi * 3 * p) * (1 - p)
                elif k == "jump":
                    y_off -= 0.07 * _bump(p * 1.15 - 0.1)
                    squash *= 1 - 0.06 * _bump(p * 6) if p < 0.16 else 1 + 0.04 * _bump(p)
                elif k == "bounce":
                    y_off -= 0.022 * abs(math.sin(2 * math.pi * 2 * p))
                elif k == "flinch":
                    lean -= 9 * a.toward * _bump(p)
                    squash *= 1 - 0.03 * _bump(p)
                elif k == "slump":
                    head_dy += 0.02
                    squash *= 0.975
                elif k == "lean_in":
                    lean += 7 * a.toward
                elif k == "lean_back":
                    lean -= 6 * a.toward
                elif k == "stomp":
                    y_off -= 0.03 * _bump(p * 2) if p < 0.5 else 0
                    squash *= 1 - 0.04 * _bump(max(0, p * 2 - 1))
            bs = a.body_s.step([lean, tilt, head_dy, look, squash], dt)
            pose.lean, pose.tilt, pose.head_dy, pose.look, pose.squash = [float(v) for v in bs]
            # ---- hands
            ga = _active(acts, "gesture", t)
            g = GEST.get(ga["gesture"], {}) if ga else {}
            near = "r" if a.toward > 0 else "l"
            far = "l" if near == "r" else "r"
            spec = {near: g.get("n", REST), far: g.get("f", REST)}
            held = None
            for h in scene.get("hands", []):
                if h["char"] == n and h["t0"] <= t < h["t1"]:
                    held = h["name"]
            if held:
                pose.holding, pose.hold_side = held, far
                if spec[far] == REST:
                    spec[far] = HOLD
            tgt = []
            for sd in ("l", "r"):
                p = self.A[n]._abs(sd, spec[sd], pose.head_dy)
                if g.get("beat") and sd == near:
                    rest = a._abs(sd, REST, 0)
                    k = min(1.0, 0.25 + env * 1.6) if talking else 0.2
                    p = [rest[0] + (p[0] - rest[0]) * k, rest[1] + (p[1] - rest[1]) * k]
                osc = g.get("osc")
                if osc and (osc[0] == "both" or (osc[0] == "n" and sd == near)):
                    L = sum(a.toon.arm)
                    ph = 2 * math.pi * osc[3] * t
                    sgn = -1 if sd == "l" else 1
                    p = [p[0] + sgn * osc[1] * L * math.sin(ph), p[1] + osc[2] * L * math.sin(ph)]
                if not ga and not held:
                    p = [p[0], p[1] + 0.004 * math.sin(t * 1.7 + a.phase + (sd == "l"))]
                tgt += p
            hs = a.hand_s.step(tgt, dt)
            pose.hands = {"l": ("abs", float(hs[0]), float(hs[1])), "r": ("abs", float(hs[2]), float(hs[3]))}
            # ---- face details
            pose.blink = a.blink_at(t) if ename not in ("laugh", "love") else 1.0
            mi = min(fi, len(self.mouth) - 1) if self.mouth else 0
            pose.mouth = self.mouth[mi] if (talking and self.mouth) else "X"
            pose.worn = [w["name"] for w in scene.get("worn", []) if w["char"] == n and w["t0"] <= t < w["t1"]]
            pose.sit = 1.0 if scene.get("sit") else 0.0
            out[n] = (pose, y_off)
        return out
