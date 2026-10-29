"""Long jobs (listening, making a video) run here, independent of the browser page.
If the page reloads, the Mac's screen turns off, or the tab is closed, the job keeps going and the page
picks up its progress again. Your inputs are saved as a draft so nothing you entered is lost."""
import json
import shutil
import threading
import time
import traceback

from .paths import WORK

DRAFT_DIR = WORK / "draft"
DRAFT = DRAFT_DIR / "draft.json"
_lock = threading.Lock()
JOB = {"id": 0, "kind": None, "running": False, "log": [], "result": None, "error": None, "started": 0,
       "progress": 0.0, "cancel": False, "stopped": False}
LIVE = WORK / "live.jpg"


def load_draft():
    try:
        return json.loads(DRAFT.read_text())
    except Exception:
        return {}


def save_draft(**kv):
    with _lock:
        DRAFT_DIR.mkdir(parents=True, exist_ok=True)
        d = load_draft()
        if "audio" in kv and kv["audio"]:
            src = str(kv["audio"])
            if not src.startswith(str(DRAFT_DIR)):
                # keep our own copy: the browser's upload cache can be cleared
                ext = src.rsplit(".", 1)[-1] if "." in src else "wav"
                for old in DRAFT_DIR.glob("audio.*"):
                    old.unlink()
                dst = DRAFT_DIR / f"audio.{ext}"
                shutil.copy(src, dst)
                kv["audio"] = str(dst)
        d.update(kv)
        DRAFT.write_text(json.dumps(d, ensure_ascii=False, default=str))
        return d.get("audio")


def start(kind, fn, *args, on_done=None, **kw):
    """Returns (started, message)."""
    with _lock:
        if JOB["running"]:
            return False, f"Still busy with the previous job ({JOB['kind']}). It keeps running — please wait."
        JOB.update(id=JOB["id"] + 1, kind=kind, running=True, log=[], result=None, error=None, started=time.time(),
                   progress=0.0, cancel=False, stopped=False)
        LIVE.unlink(missing_ok=True)
        jid = JOB["id"]

    def log(m):
        JOB["log"].append(str(m))
        del JOB["log"][:-40]

    def work():
        try:
            res = fn(*args, log=log, **kw)
            JOB["result"] = res
            if on_done:
                on_done(res)
        except Exception as e:
            if type(e).__name__ == "Stopped":
                JOB["stopped"] = True
                log("⏹ Stopped. Nothing was saved; your inputs are still here.")
                return
            JOB["error"] = str(e)
            log("⚠️ " + str(e))
            traceback.print_exc()
        finally:
            JOB["running"] = False

    threading.Thread(target=work, daemon=True, name=f"job-{jid}").start()
    return True, ""


def progress(p):
    JOB["progress"] = float(p)


def stop_requested():
    return JOB["cancel"]


def request_stop():
    if JOB["running"]:
        JOB["cancel"] = True
        return True
    return False


def status():
    return dict(JOB)
