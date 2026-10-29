"""Where things live.

App code (this folder) and YOUR data are kept apart, so the app can be updated or replaced at any time
without touching your characters, videos, props or settings:
  ~/Documents/Toonbox Data/
      library/characters, library/props, library/locations   your cast and assets
      videos/                                                finished videos
      settings.json, models/, tools/, work/                  settings, downloads, temporary files
"""
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent           # the app
DATA = Path(os.environ.get("TOONBOX_DATA", Path.home() / "Documents" / "Toonbox Data"))
LIBRARY = DATA / "library"
CHARACTERS = LIBRARY / "characters"
LOCATIONS = LIBRARY / "locations"
VIDEOS = DATA / "videos"
TOOLS = DATA / "tools"
WORK = DATA / "work"
SETTINGS = DATA / "settings.json"
MODELS = DATA / "models"
STARTER = ROOT / "starter"

for _d in (CHARACTERS, LOCATIONS, VIDEOS, TOOLS, WORK, MODELS):
    _d.mkdir(parents=True, exist_ok=True)


def _first_run():
    # bring over data kept inside an older app folder (v3 / v3.1), then add the starter cast if empty
    for name in ("library", "videos"):
        old = ROOT / name
        if old.is_dir():
            for f in old.rglob("*"):
                if f.is_file():
                    dst = DATA / name / f.relative_to(old)
                    if not dst.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, dst)
    if not any(CHARACTERS.iterdir()) and (STARTER / "characters").is_dir():
        shutil.copytree(STARTER / "characters", CHARACTERS, dirs_exist_ok=True)


try:
    _first_run()
except Exception:
    pass

DEFAULT_SETTINGS = {
    "claude_api_key": "",
    "claude_model": "claude-sonnet-5-5",
    "whisper_model": "large-v3-turbo",
    "fps": 24,
}


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    try:
        s.update(json.loads(SETTINGS.read_text()))
    except Exception:
        pass
    return s


def save_settings(s):
    SETTINGS.write_text(json.dumps(s, indent=2))


def ffmpeg_exe():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"
