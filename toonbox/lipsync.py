"""Mouth timing: Rhubarb Lip Sync when installed, otherwise a built-in loudness-based version."""
import json
import platform
import subprocess

import numpy as np

from . import audio
from .paths import TOOLS, WORK


def rhubarb_path():
    for p in TOOLS.glob("rhubarb*/rhubarb"):
        return p
    for p in TOOLS.glob("**/rhubarb"):
        if p.is_file():
            return p
    return None


def _rhubarb(wav, english, log):
    exe = rhubarb_path()
    if exe is None:
        return None
    out = WORK / "mouth.json"
    cmd = [str(exe), "-q", "-f", "json", "-o", str(out), "-r", "pocketSphinx" if english else "phonetic", str(wav)]
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        cmd = ["arch", "-x86_64"] + cmd  # Rhubarb's Mac build runs through Rosetta
    try:
        log("Timing mouth shapes with Rhubarb…")
        subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
        return json.loads(out.read_text())["mouthCues"]
    except Exception as e:
        log(f"Rhubarb didn't run ({type(e).__name__}); using built-in lip-sync.")
        return None


def _builtin(path, fps):
    env, dur = audio.envelope(path, fps)
    if env.max() <= 0:
        return ["X"] * len(env)
    ref = np.percentile(env[env > 0], 95)
    e = np.clip(env / (ref + 1e-9), 0, 1.2)
    shapes = []
    rng = np.random.default_rng(7)
    prev = "X"
    hold = 0
    for i, v in enumerate(e):
        if v < 0.10:
            s = "X"
        elif v < 0.22:
            s = rng.choice(["B", "A", "G"], p=[0.6, 0.2, 0.2])
        elif v < 0.45:
            s = rng.choice(["C", "B", "H", "F"], p=[0.5, 0.2, 0.15, 0.15])
        elif v < 0.7:
            s = rng.choice(["C", "D", "E"], p=[0.4, 0.4, 0.2])
        else:
            s = rng.choice(["D", "E"], p=[0.75, 0.25])
        if s != prev and hold < 2 and prev != "X":
            s = prev  # hold each shape at least 2 frames so it doesn't flicker
            hold += 1
        else:
            hold = 0 if s != prev else hold + 1
        shapes.append(str(s))
        prev = s
    return shapes


def mouth_track(path, fps, language, log=print):
    """Returns a mouth shape letter for every video frame of the whole audio."""
    WORK.mkdir(exist_ok=True)
    wav = audio.to_wav(path, WORK / "speech.wav")
    cues = _rhubarb(wav, english=(language or "").lower().startswith("en"), log=log)
    _, dur = audio.envelope(path, fps)
    n = int(dur * fps) + 2
    if cues:
        shapes = ["X"] * n
        for c in cues:
            for f in range(int(c["start"] * fps), min(n, int(c["end"] * fps) + 1)):
                shapes[f] = c["value"]
        return shapes, "Rhubarb"
    log("Using built-in lip-sync (follows loudness).")
    return _builtin(path, fps), "built-in"
