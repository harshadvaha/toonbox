"""Your saved characters (the cast of your series).

Each character lives in library/characters/<id>/:
  v1.json, v2.json …  the look (every save is a new version; old ones are kept)
  voice.json          voice memory, learned from finished videos, used to tell speakers apart
  preview.png         picture shown in the app
"""
import json
import re
import shutil
import time

from . import toon
from .paths import CHARACTERS


def slug(s):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").strip().lower()).strip("-")
    return s or "item"


def _dir(cid):
    return CHARACTERS / cid


def _versions(cid):
    vs = []
    for f in _dir(cid).glob("v*.json"):
        try:
            vs.append(int(f.stem[1:]))
        except ValueError:
            pass
    return sorted(vs)


def list_characters():
    out = []
    for d in sorted(CHARACTERS.iterdir()) if CHARACTERS.exists() else []:
        if d.is_dir() and _versions(d.name):
            try:
                out.append(load(d.name))
            except Exception:
                pass
    return sorted(out, key=lambda m: m["name"].lower())


def names():
    return [c["name"] for c in list_characters()]


def name_to_id():
    return {c["name"]: c["id"] for c in list_characters()}


def load(cid, version=None):
    vs = _versions(cid)
    v = version or vs[-1]
    spec = json.loads((_dir(cid) / f"v{v}.json").read_text())
    spec["id"], spec["version"] = cid, v
    return spec


def by_name(name):
    cid = name_to_id().get(name)
    return load(cid) if cid else None


def save(spec, as_new=False):
    """Save the look. Same name = new version of that character; returns (id, version)."""
    spec = {k: v for k, v in spec.items() if k not in ("id", "version")}
    spec["name"] = (spec.get("name") or "New character").strip()
    existing = name_to_id()
    cid = None if as_new else existing.get(spec["name"])
    if cid is None:
        base = slug(spec["name"])
        cid, i = base, 2
        while _dir(cid).exists():
            cid = f"{base}-{i}"
            i += 1
        if as_new and spec["name"] in existing:
            spec["name"] = f'{spec["name"]} {i - 1}'
    d = _dir(cid)
    d.mkdir(parents=True, exist_ok=True)
    vs = _versions(cid)
    v = (vs[-1] + 1) if vs else 1
    spec["saved"] = time.strftime("%Y-%m-%d %H:%M")
    (d / f"v{v}.json").write_text(json.dumps(spec, indent=2))
    try:
        toon.sheet(spec).save(d / "preview.png")
    except Exception:
        pass
    return cid, v


def export(cid):
    """One file with the look + voice memory, for backup or another Mac."""
    spec = load(cid)
    data = {"toonbox_character": 1, "look": {k: v for k, v in spec.items() if k not in ("id", "version")},
            "voice": voice(cid)}
    out = _dir(cid) / f'{slug(spec["name"])}.toonchar.json'
    out.write_text(json.dumps(data, indent=2))
    return out


def import_file(path):
    data = json.loads(open(path, encoding="utf-8").read())
    look = data.get("look", data)
    cid, v = save(look)
    if data.get("voice"):
        (_dir(cid) / "voice.json").write_text(json.dumps(data["voice"]))
    return load(cid)


def remove(cid):
    """Moves a character to library/removed (not deleted, so it can be restored)."""
    dst = CHARACTERS.parent / "removed" / f"{cid}-{int(time.time())}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(_dir(cid)), str(dst))


# ------------------------------------------------------------------ voice memory
def voice(cid):
    try:
        return json.loads((_dir(cid) / "voice.json").read_text())
    except Exception:
        return None


def remember_voice(cid, pitch, vec, n_lines):
    """Running average of the character's voice, from lines confirmed in a finished video."""
    old = voice(cid)
    if old and old.get("n"):
        n0 = old["n"]
        w = n0 / (n0 + n_lines)
        pitch = old["pitch"] * w + pitch * (1 - w)
        vec = [a * w + b * (1 - w) for a, b in zip(old["vec"], vec)]
        n_lines += n0
    (_dir(cid) / "voice.json").write_text(json.dumps({"pitch": float(pitch), "vec": [float(x) for x in vec],
                                                      "n": int(n_lines)}))
