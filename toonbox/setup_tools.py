"""First-run helper: downloads Rhubarb Lip Sync (free, open source) into the tools folder."""
import io
import platform
import subprocess
import urllib.request
import zipfile

from .paths import TOOLS

VER = "1.14.0"


def speech_model():
    """Download the speech-to-text model once, here in the setup window (not inside the app)."""
    from .paths import MODELS, load_settings
    name = load_settings().get("whisper_model", "large-v3-turbo")
    flag = MODELS / f".ready-{name}"
    if flag.exists():
        return
    print(f"Downloading the speech-to-text model ({name}, about 1.6 GB, one time). Please keep this window open…")
    try:
        from faster_whisper import WhisperModel
        WhisperModel(name, device="cpu", compute_type="int8", download_root=str(MODELS))
        flag.write_text("ok")
        print("Speech-to-text model ready.")
    except Exception as e:
        print(f"Couldn't download the speech model now ({e}). The app will try again when you first use it.")


def main():
    speech_model()
    if any(TOOLS.glob("**/rhubarb")):
        return
    sysname = {"Darwin": "macOS", "Linux": "Linux", "Windows": "Windows"}.get(platform.system())
    if not sysname:
        return
    url = (f"https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v{VER}/"
           f"Rhubarb-Lip-Sync-{VER}-{sysname}.zip")
    print("Downloading Rhubarb Lip Sync (one time, ~85 MB)…")
    try:
        data = urllib.request.urlopen(url, timeout=120).read()
        zipfile.ZipFile(io.BytesIO(data)).extractall(TOOLS)
        for p in TOOLS.glob("**/rhubarb"):
            p.chmod(0o755)
        if sysname == "macOS" and platform.machine() == "arm64":
            ok = subprocess.run(["arch", "-x86_64", "/usr/bin/true"], capture_output=True).returncode == 0
            if not ok:
                print("Rhubarb needs Apple's Rosetta. Installing it (you may be asked for your password)…")
                subprocess.run(["softwareupdate", "--install-rosetta", "--agree-to-license"])
        print("Rhubarb ready.")
    except Exception as e:
        print(f"Couldn't set up Rhubarb ({e}). That's OK — the built-in lip-sync will be used.")


if __name__ == "__main__":
    main()
