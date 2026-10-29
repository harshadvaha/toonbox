"""Glue: audio + saved characters + notes -> lines -> storyboard -> finished MP4 in the videos folder."""
import itertools
import json
import time

import numpy as np

from . import audio, cast, director, lipsync
from .cast import slug
from .paths import VIDEOS, load_settings
from .render import Stage, render_video

LANGS = {"Auto-detect": None, "Hindi": "hi", "English": "en", "Gujarati": "gu", "Marathi": "mr", "Tamil": "ta",
         "Telugu": "te", "Bengali": "bn", "Punjabi": "pa", "Urdu": "ur"}


def _features(path, lines):
    y = audio.load_wav(path)
    feats = []
    for l in lines:
        a, b = int(l["start"] * audio.SR), int(l["end"] * audio.SR)
        c = y[a:b]
        if len(c) < audio.SR * 0.4:
            m = (a + b) // 2
            c = y[max(0, m - int(audio.SR * 0.3)): m + int(audio.SR * 0.3)]
        v = audio._mfcc_pitch(c)
        feats.append((float(audio._pitch(c)), v[:-1]))
    return feats


def _match_voices(path, lines, speaking, log):
    """Use saved voice memory to decide which voice group is which character."""
    k = len(speaking)
    mem = {n: cast.voice(cast.name_to_id().get(n, "")) for n in speaking}
    if k < 2 or not all(mem.values()):
        return None
    feats = _features(path, lines)
    groups = {}
    for l, (p, v) in zip(lines, feats):
        groups.setdefault(l["speaker"], []).append((p, v))
    cents = {g: (np.median([p for p, _ in fs]), np.mean([v for _, v in fs], 0)) for g, fs in groups.items()}

    def cost(g, n):
        p, v = cents[g]
        m = mem[n]
        mv = np.array(m["vec"])
        cos = 1 - float(np.dot(v, mv) / (np.linalg.norm(v) * np.linalg.norm(mv) + 1e-9))
        return abs(p - m["pitch"]) * 3 + cos

    gs = sorted(cents)
    best = min(itertools.permutations(speaking, len(gs)), key=lambda perm: sum(cost(g, n) for g, n in zip(gs, perm)))
    log("Matched voices to characters using their saved voice memory.")
    return dict(zip(gs, best))


def analyze(audio_path, speaking, language, log=print):
    """Step 1: find lines and who says them. Returns rows for the review table."""
    s = load_settings()
    lines, has_text = audio.transcribe(audio_path, LANGS.get(language), s.get("whisper_model", "large-v3-turbo"), log)
    if not lines:
        raise RuntimeError("No speech found in the audio.")
    lines = audio.assign_speakers(audio_path, lines, max(1, len(speaking)), log)
    lines = audio.loudness(audio_path, lines)
    mapping = None
    try:
        mapping = _match_voices(audio_path, lines, speaking, log)
    except Exception as e:
        log(f"(voice memory skipped: {type(e).__name__})")
    rows = []
    for l in lines:
        if mapping:
            who = mapping.get(l["speaker"], speaking[0])
        else:
            who = speaking[l["speaker"]] if l["speaker"] < len(speaking) else speaking[-1]
        rows.append([f'{l["start"]:.2f}', f'{l["end"]:.2f}', who, l["text"], l["loud"]])
    if not mapping and len(speaking) > 1:
        log("Tip: voices are matched in the order they first speak. Fix the 'Who' column if needed — "
            "after this video the app remembers each voice.")
    return rows


def rows_to_lines(rows, speaking):
    lines = []
    for r in rows:
        try:
            st, en, who, text = float(r[0]), float(r[1]), str(r[2]).strip(), str(r[3] or "")
            loud = float(r[4]) if len(r) > 4 and r[4] not in ("", None) else 0.0
        except Exception:
            continue
        if who not in speaking:
            match = [s for s in speaking if s.lower() == who.lower()]
            who = match[0] if match else speaking[0]
        lines.append({"start": st, "end": en, "speaker": who, "text": text, "loud": loud})
    return sorted(lines, key=lambda l: l["start"])


def add_pitch(audio_path, lines):
    feats = _features(audio_path, lines)
    by = {}
    for l, (p, _) in zip(lines, feats):
        l["_p"] = p
        by.setdefault(l["speaker"], []).append(p)
    for l in lines:
        ps = by[l["speaker"]]
        sd = np.std(ps) if len(ps) > 2 else 0.0
        l["pz"] = round(float((l["_p"] - np.mean(ps)) / sd), 2) if sd > 1e-3 else 0.0
        del l["_p"]
    return lines, feats


def learn_voices(lines, feats):
    ids = cast.name_to_id()
    for name in {l["speaker"] for l in lines}:
        fs = [f for l, f in zip(lines, feats) if l["speaker"] == name and l["end"] - l["start"] >= 0.4]
        if name in ids and fs:
            cast.remember_voice(ids[name], float(np.median([p for p, _ in fs])),
                                list(np.mean([v for _, v in fs], 0)), len(fs))


def _out_path(title):
    stamp = time.strftime("%Y-%m-%d_%H%M")
    base = f"{stamp}_{slug(title) if title.strip() else 'video'}"
    p = VIDEOS / f"{base}.mp4"
    i = 2
    while p.exists():  # never overwrite an earlier video
        p = VIDEOS / f"{base}_v{i}.mp4"
        i += 1
    return p


def make_video(audio_path, rows, speaking, silent, locations, notes, title, fmt, language, subtitles,
               log=print, progress=None, out=None, start=0.0, end=None, stop=None, live=None):
    s = load_settings()
    fps = int(s.get("fps", 24))
    size = (1080, 1920) if fmt.startswith("Vertical") else (1920, 1080)
    who = list(dict.fromkeys(speaking + [c for c in silent if c not in speaking]))
    specs = []
    for n in who:
        spec = cast.by_name(n)
        if spec is None:
            raise RuntimeError(f"Character '{n}' isn't saved. Create it in the Characters tab first.")
        specs.append(spec)
    lines = rows_to_lines(rows, speaking)
    feats = None
    try:
        lines, feats = add_pitch(audio_path, lines)
    except Exception:
        pass
    env, duration = audio.envelope(audio_path, fps)
    env = np.clip(env / (np.percentile(env[env > 0], 95) + 1e-9), 0, 1.2) if env.max() > 0 else env
    mouth, how = lipsync.mouth_track(audio_path, fps, LANGS.get(language) or "", log)
    plan = director.make_plan(lines, who, locations or ["Auto"], notes, duration, s, log)
    sc = plan["scenes"]
    log(f"Storyboard ready ({plan['by']} director): {len(sc)} scene(s) in " +
        ", ".join(x["location"] for x in sc) + f", {len(plan['shots'])} camera shots.")
    stage = Stage(specs, plan, lines, mouth, env, fps, size, title=title, subtitles=subtitles)
    out = out or _out_path(title)
    log(f"Drawing {stage.frames} frames…")
    render_video(stage, audio_path, out, progress, log, start=start, end=end, stop=stop, live=live)
    side = out.with_suffix(".storyboard.json")
    side.write_text(json.dumps({"lines": lines, "plan": plan, "cast": who, "lip_sync": how,
                                "audio": str(audio_path)}, indent=2, ensure_ascii=False, default=str))
    if feats:
        try:
            learn_voices(lines, feats)
        except Exception:
            pass
    log(f"Done → {out.name}")
    return out
