"""Puts it all together on screen: background, props, characters, emotes, camera, captions -> MP4."""
import math
import subprocess

import numpy as np
import skia
from PIL import Image

from . import backgrounds, emotes, props as P
from .anim import Actor, Animator
from .paths import ffmpeg_exe
from .toon import Toon, _font

WIDTH = {"blob": 0.74, "clothes": 0.5, "stick": 0.46}


def _skimg(pil):
    a = np.asarray(pil.convert("RGBA")).copy()
    return skia.Image.fromarray(a, colorType=skia.kRGBA_8888_ColorType)


class Stage:
    def __init__(self, specs, plan, lines, mouth, env, fps, size, title="", subtitles=False):
        self.W, self.H = size
        self.fps = fps
        self.plan, self.lines = plan, lines
        self.title, self.subtitles = title, subtitles
        self.vertical = self.H > self.W
        self.toons = [Toon(s) for s in specs]
        self.names = [s["name"] for s in specs]
        self.actors = self._layout()
        self.anim = Animator(self.actors, plan, lines, mouth, env, fps)
        self._bg = {}
        self.duration = plan["duration"]
        self.frames = int(math.ceil(self.duration * fps)) + fps // 2  # whole audio + a short tail
        self.rng = np.random.default_rng(5)

    # ------------------------------------------------------------------ layout
    def _layout(self):
        n = len(self.toons)
        W, H = self.W, self.H
        widths = [WIDTH[t.style] * float(t.spec.get("width", 1)) * float(t.spec.get("height", 1)) for t in self.toons]
        gap = 0.1
        hmax = (0.47 if self.vertical else 0.72) * H
        h = min(hmax, W * 0.92 / (sum(widths) + gap * max(0, n - 1)))
        self.feet_y = H * (0.9 if self.vertical else 0.93)
        total = (sum(widths) + gap * max(0, n - 1)) * h
        x = W / 2 - total / 2
        actors = []
        for i, (t, wd) in enumerate(zip(self.toons, widths)):
            cx = x + wd * h / 2
            hh = h * float(t.spec.get("height", 1))
            actors.append(Actor(self.names[i], t, cx, hh, self.fps, seed=11 + i * 7))
            x += (wd + gap) * h
        self.h = h
        return actors

    def _background(self, loc):
        if loc not in self._bg:
            im = backgrounds.render(loc, self.W * 2, self.H * 2)
            self._bg[loc] = _skimg(im)
        return self._bg[loc]

    # ------------------------------------------------------------------ camera
    def _box(self, who=None, close=False, scene=None):
        acts = [a for a in self.actors if who is None or a.name == who]
        if close:
            a = acts[0]
            top = self.feet_y - a.h * 1.06
            sit = scene and scene.get("sit")
            top += a.h * 0.17 if sit else 0
            return a.x - a.h * 0.42, top, a.x + a.h * 0.42, top + a.h * 0.68
        l = min(a.x - a.h * WIDTH[a.toon.style] * 0.42 for a in acts)
        r = max(a.x + a.h * WIDTH[a.toon.style] * 0.42 for a in acts)
        top = min(self.feet_y - a.h * 1.12 for a in acts)
        bottom = self.feet_y - self.h * 0.24  # knees up: bigger characters, like a sitcom frame
        if scene and scene.get("floor"):
            bottom = self.feet_y + self.h * 0.04
        if scene and scene.get("front"):
            bottom = self.feet_y - self.h * 0.1
        return l, top, r, bottom

    def _camera(self, shot, t, scene):
        close = shot["kind"] == "close" and shot.get("focus") in self.names
        l, tp, r, b = self._box(shot.get("focus") if close else None, close, scene)
        bw, bh = r - l, b - tp
        z = min(self.W / bw, self.H / bh * (0.86 if close else 0.8))
        z = max(1.0, min(z, 2.4))
        p = (t - shot["start"]) / max(0.3, shot["end"] - shot["start"])
        z *= 1 + shot.get("push", 0.03) * p
        cx = (l + r) / 2
        cy = (tp + b) / 2 + (self.H / z) * (0.06 if close else 0.04)
        hw, hh = self.W / z / 2, self.H / z / 2
        cx = min(max(cx, hw), self.W - hw)
        cy = min(max(cy, hh), self.H - hh)
        sh = shot.get("shake")
        if sh and sh[0] <= t <= sh[1]:
            k = 1 - (t - sh[0]) / max(0.05, sh[1] - sh[0])
            cx += self.rng.normal() * self.W * 0.006 * k
            cy += self.rng.normal() * self.H * 0.004 * k
        return z, cx, cy

    def _shot(self, t):
        cur = self.plan["shots"][0]
        for s in self.plan["shots"]:
            if s["start"] <= t:
                cur = s
        return cur

    def _scene(self, t):
        return self.anim.scene_at(t)

    # ------------------------------------------------------------------ props placement
    def _back_props(self, cv, scene, t):
        slots_side = [self.W * 0.08, self.W * 0.92, self.W * 0.5]
        side_i = 0
        sit = scene.get("sit")
        for name in scene.get("back", []):
            if name in ("chair", "office chair"):
                if sit or scene.get("front") == "desk":
                    for a in self.actors:
                        P.draw(cv, name, a.x, self.feet_y - a.h * 0.02, a.h)
                else:
                    x = slots_side[side_i % 3]
                    side_i += 1
                    P.draw(cv, name, x, self.feet_y - self.h * 0.06, self.h * 0.9)
            elif name in ("sofa", "bed"):
                xs = [a.x for a in self.actors]
                w = (max(xs) - min(xs)) / self.h + 0.8
                P.draw(cv, name, sum(xs) / len(xs), self.feet_y - self.h * 0.03, self.h, w=w)
            else:
                x = slots_side[side_i % 2]
                side_i += 1
                P.draw(cv, name, x, self.feet_y - self.h * 0.07, self.h * 0.92)

    def _front_props(self, cv, scene):
        f = scene.get("front")
        if not f:
            return
        sit = scene.get("sit")
        top = 0.27 if sit else 0.4
        kw = {}
        if f == "desk":
            xs = [(a.x - self.W / 2) / self.h for a in self.actors]
            if scene.get("desk_items") == "laptops":
                kw["laptops"] = xs
            elif scene.get("desk_items") == "monitor":
                kw["monitor"] = xs
        P.draw_front(cv, f, self.W / 2, self.feet_y + self.h * 0.03, self.h, (self.W * 1.3) / self.h, top + 0.03, **kw)

    def _floor_props(self, cv, scene, t):
        for i, fp in enumerate(scene.get("floor", [])):
            if not (fp["t0"] <= t < fp["t1"]):
                continue
            near = next((a for a in self.actors if a.name == fp.get("near")), None)
            if near is None:
                near = self.actors[i % len(self.actors)]
            out_side = -1 if near.x < self.W / 2 else 1
            if len(self.actors) == 1:
                out_side = 1
            x_end = near.x + out_side * near.h * 0.42
            x = x_end
            walking = False
            if fp.get("enter"):
                p = (t - fp["t0"]) / 1.4
                if p < 1:
                    x0 = self.W / 2 + out_side * (self.W / 2 + self.h * 0.4)
                    e = 1 - (1 - p) ** 2
                    x = x0 + (x_end - x0) * e
                    walking = True
            flip = out_side > 0
            kw = {"t": t, "walking": walking} if fp["name"] in ("dog", "cat") else {}
            if fp["name"] in ("dog", "cat"):
                kw["flip"] = flip
            P.draw(cv, fp["name"], x, self.feet_y + self.h * 0.05, self.h * 1.05, **kw)

    # ------------------------------------------------------------------ frame
    def frame(self, fi, surf):
        t = fi / self.fps
        cv = surf.getCanvas()
        scene = self._scene(t)
        shot = self._shot(t)
        z, cx, cy = self._camera(shot, t, scene)
        poses = self.anim.step(fi)
        cv.save()
        cv.translate(self.W / 2, self.H / 2)
        cv.scale(z, z)
        cv.translate(-cx, -cy)
        bg = self._background(scene["location"])
        cv.drawImageRect(bg, skia.Rect.MakeWH(self.W, self.H), skia.SamplingOptions(skia.FilterMode.kLinear))
        # soft floor shadow strip so characters sit in the room
        self._back_props(cv, scene, t)
        for a in self.actors:
            pose, y_off = poses[a.name]
            sh = skia.Paint(Color=skia.ColorSetARGB(40, 0, 0, 0), AntiAlias=True)
            if not scene.get("front"):
                cv.drawOval(skia.Rect.MakeLTRB(a.x - a.h * 0.2, self.feet_y - a.h * 0.02, a.x + a.h * 0.2,
                                               self.feet_y + a.h * 0.02), sh)
            a.toon.draw(cv, a.x, self.feet_y + y_off * a.h, a.h, pose)
        self._front_props(cv, scene)
        self._floor_props(cv, scene, t)
        self._emotes(cv, t)
        cv.restore()
        if self.subtitles:
            self._subtitle(cv, t)
        if self.title:
            self._title(cv)

    def _emotes(self, cv, t):
        for e in self.plan.get("emotes", []):
            if not (e["t"] <= t < e["t"] + e["dur"]):
                continue
            a = next((x for x in self.actors if x.name == e["char"]), None)
            if a is None:
                continue
            p = (t - e["t"]) / e["dur"]
            size = int(a.h * 0.2)
            s = 1.0
            if p < 0.15:
                s = 0.3 + 0.95 * math.sin(p / 0.15 * math.pi / 2) + 0.15 * math.sin(p / 0.15 * math.pi)
            alpha = 1.0 if p < 0.8 else max(0.0, 1 - (p - 0.8) / 0.2)
            img = emotes.draw(e["name"], size)
            key = ("emote", e["name"], size)
            sk = self._bg.get(key)
            if sk is None:
                sk = self._bg[key] = _skimg(img)
            side = 1 if a.toward < 0 else -1
            x = a.x + side * a.h * 0.22
            y = self.feet_y - a.h * 1.08 + math.sin(t * 6) * a.h * 0.005
            w = size * s
            paint = skia.Paint(Alphaf=alpha)
            cv.drawImageRect(sk, skia.Rect.MakeXYWH(x - w / 2, y - w / 2, w, w),
                             skia.SamplingOptions(skia.FilterMode.kLinear), paint)

    def _subtitle(self, cv, t):
        txt = None
        for l in self.lines:
            if l["start"] - 0.05 <= t <= l["end"] + 0.25 and l.get("text"):
                txt = l["text"]
        if not txt:
            return
        size = self.W * (0.05 if self.vertical else 0.032)
        font = _font(size)
        words = txt.split()
        rows, cur = [], ""
        maxw = self.W * 0.82
        for w in words:
            test = (cur + " " + w).strip()
            if font.measureText(test) > maxw and cur:
                rows.append(cur)
                cur = w
            else:
                cur = test
        rows.append(cur)
        y = self.H * (0.13 if self.vertical else 0.86)
        for r in rows[:3]:
            tw = font.measureText(r)
            x = (self.W - tw) / 2
            blob = skia.TextBlob(r, font)
            cv.drawTextBlob(blob, x, y, skia.Paint(Color=skia.ColorSetARGB(255, 20, 20, 24), AntiAlias=True,
                                                   Style=skia.Paint.kStroke_Style, StrokeWidth=size * 0.16,
                                                   StrokeJoin=skia.Paint.kRound_Join))
            cv.drawTextBlob(blob, x, y, skia.Paint(Color=skia.ColorSetARGB(255, 255, 255, 255), AntiAlias=True))
            y += size * 1.25

    def _title(self, cv):
        size = self.W * (0.055 if self.vertical else 0.035)
        font = _font(size)
        tw = font.measureText(self.title)
        pad = size * 0.5
        y = self.H * 0.07
        r = skia.Rect.MakeLTRB((self.W - tw) / 2 - pad, y - size - pad * 0.4, (self.W + tw) / 2 + pad, y + pad * 0.8)
        cv.drawRRect(skia.RRect.MakeRectXY(r, size * 0.3, size * 0.3), skia.Paint(Color=skia.ColorSetARGB(235, 18, 18, 22),
                                                                                   AntiAlias=True))
        cv.drawString(self.title, (self.W - tw) / 2, y, font, skia.Paint(Color=skia.ColorSetARGB(255, 255, 255, 255),
                                                                          AntiAlias=True))


class Stopped(Exception):
    pass


def render_video(stage, audio_path, out_path, progress=None, log=print, start=0.0, end=None, stop=None, live=None):
    W, H, fps = stage.W, stage.H, stage.fps
    f0 = int(start * fps)
    f1 = stage.frames if end is None else min(stage.frames, int(end * fps))
    cmd = [ffmpeg_exe(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(fps),
           "-i", "-", "-ss", f"{start:.3f}", "-i", str(audio_path), "-map", "0:v", "-map", "1:a", "-af", "apad", "-c:v", "libx264",
           "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest",
           "-movflags", "+faststart", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(W, H, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))
    for fi in range(0, f1):
        if fi < f0:
            stage.anim.step(fi)  # keep the motion continuous when starting mid-way
            continue
        surf.getCanvas().clear(skia.ColorSetARGB(255, 255, 255, 255))
        stage.frame(fi, surf)
        snap = surf.makeImageSnapshot()
        proc.stdin.write(snap.tobytes())
        if progress and fi % 12 == 0:
            progress((fi - f0) / max(1, f1 - f0))
        if live and fi % fps == 0:  # a small picture of the current frame for the app's live view
            try:
                a = snap.toarray()[..., :3]
                Image.fromarray(a[::3, ::3].copy()).save(live)
            except Exception:
                pass
        if stop and stop():
            proc.stdin.close()
            proc.kill()
            proc.wait()
            try:
                out_path.unlink()
            except Exception:
                pass
            raise Stopped()
        if fi % (fps * 10) == 0 and fi > f0:
            log(f"…{int(fi / fps)} s drawn")
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        raise RuntimeError("Video encoder failed.")
    return out_path
