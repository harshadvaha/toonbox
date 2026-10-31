"""Toonbox v3 — simple browser app. Run with start.command (Mac) or: uv run python -m toonbox.app"""
import queue
import threading
import time
import traceback
from pathlib import Path

import gradio as gr
import numpy as np
import skia
from PIL import Image

from . import backgrounds, cast, jobs, lipsync, pipeline, props, toon
from .paths import ROOT, DATA, VIDEOS, WORK, load_settings, save_settings

CSS = """
.gradio-container {max-width: 1220px !important}
#title h1 {font-size: 2rem; margin-bottom: 0; letter-spacing: -0.5px}
#title p {color: #5b6472; margin-top: 4px}
.step-btn {min-height: 52px; font-size: 1.05rem !important}
"""
THEME = gr.themes.Soft(primary_hue="teal", secondary_hue="indigo", neutral_hue="slate")


def _stream(fn, *args, **kw):
    """Run fn in the background and stream its log lines to the page."""
    q, box, log = queue.Queue(), {}, []

    def work():
        try:
            box["result"] = fn(*args, log=lambda m: q.put(str(m)), **kw)
        except Exception as e:
            box["error"] = e
            q.put("⚠️ " + str(e))
            traceback.print_exc()
        q.put(None)

    threading.Thread(target=work, daemon=True).start()
    while True:
        m = q.get()
        if m is None:
            break
        log.append(m)
        yield "\n".join(log[-14:]), None
    yield "\n".join(log[-14:]), box.get("error") or box.get("result")


# ---------------------------------------------------------------- New video (jobs keep running if the page reloads)
RATIOS = ["9:16 (vertical — Shorts / Reels)", "16:9 (horizontal — YouTube)"]


def _fmt(ratio):
    return "Vertical" if str(ratio).startswith("9:16") else "Horizontal"


def _rows(table):
    rows = table.values.tolist() if hasattr(table, "values") else (table or [])
    return [r for r in rows if r and str(r[0]).strip()]


def _guard():
    if jobs.stop_requested():
        from .render import Stopped
        raise Stopped()


def do_listen(audio, speaking, language):
    if not audio:
        return "Add an audio file first."
    if not speaking:
        return "Pick who speaks (at least one character)."
    audio = jobs.save_draft(audio=audio, speaking=speaking, lang=language) or audio

    def run(log):
        rows = pipeline.analyze(audio, speaking, language, log=log)
        _guard()
        return rows

    def done(rows):
        jobs.save_draft(table=rows, video=None)
    ok, msg = jobs.start("listening", run, on_done=done)
    return msg


def _make(audio, speaking, silent, locs, notes, title, ratio, language, subs, table, preview):
    if not audio or not speaking:
        return "Add an audio file and pick who speaks."
    audio = jobs.save_draft(audio=audio, speaking=speaking, silent=silent, locs=locs, notes=notes, title=title,
                            ratio=ratio, lang=language, subs=subs) or audio
    rows = _rows(table)
    kw = {"progress": jobs.progress, "stop": jobs.stop_requested, "live": jobs.LIVE}
    if preview:
        import time
        kw.update(out=WORK / f"preview_{int(time.time())}.mp4", end=15.0)
    args = (speaking, silent or [], locs or ["Auto"], notes or "", title or "", _fmt(ratio), language, subs)

    def run(log, **k):
        r = rows
        if not r:
            r = pipeline.analyze(audio, speaking, language, log=log)
            jobs.save_draft(table=r)
            _guard()
        return pipeline.make_video(audio, r, *args, log=log, **k)

    def done(out):
        jobs.save_draft(video=str(out))
    ok, msg = jobs.start("preview" if preview else "video", run, on_done=done, **kw)
    return msg


def do_make(*a):
    return _make(*a, preview=False)


def do_preview(*a):
    return _make(*a, preview=True)


def do_stop(confirmed):
    if confirmed and jobs.request_stop():
        return "Stopping…"
    return gr.update()


KIND = {"listening": "Listening to the audio", "video": "Making the video", "preview": "Making a 15-second preview"}


def _card(state, title, detail="", pct=None, colour="#0f766e"):
    bar = ""
    if pct is not None:
        bar = (f'<div style="height:10px;background:#e2e8f0;border-radius:6px;margin:10px 0 6px;overflow:hidden">'
               f'<div style="height:100%;width:{pct:.0f}%;background:{colour};border-radius:6px;'
               f'transition:width .8s"></div></div>')
    return (f'<div style="border:1px solid #e2e8f0;border-radius:12px;padding:14px 16px;background:#f8fafc">'
            f'<div style="font-size:.8rem;font-weight:700;letter-spacing:.06em;color:{colour}">{state}</div>'
            f'<div style="font-size:1.15rem;font-weight:600;margin-top:2px">{title}</div>{bar}'
            f'<div style="color:#475569;font-size:.92rem">{detail}</div></div>')


def _mmss(s):
    s = int(max(0, s))
    return f"{s // 60}:{s % 60:02d}"


def tick(seen, live_m):
    """Every second: status card, buttons, live view, and the result once a job finishes."""
    st = jobs.status()
    log = "\n".join(st["log"][-14:]) or ""
    table, video, live = gr.update(), gr.update(), gr.update()
    running = st["running"]
    if running:
        el = time.time() - st["started"]
        p = st["progress"]
        if st["kind"] == "listening":
            card = _card("WORKING", KIND["listening"], f"{_mmss(el)} so far · the first time includes a model "
                         "download. You can leave this page — it keeps going.", None)
        else:
            left = f" · about {_mmss(el / p - el)} left" if p > 0.03 else ""
            step = "Drawing frames" if p > 0 else (st["log"][-1] if st["log"] else "Getting ready")
            card = _card("WORKING", KIND[st["kind"]], f"{step} · {p * 100:.0f}% · {_mmss(el)} so far{left}. "
                         "Live view below. You can leave this page — it keeps going.", p * 100)
            try:
                m = jobs.LIVE.stat().st_mtime
                if m != live_m:
                    live_m, live = m, gr.update(value=str(jobs.LIVE), visible=True)
            except FileNotFoundError:
                pass
        if st["cancel"]:
            card = _card("STOPPING", "Stopping…", "Finishing the current frame.", None, "#b45309")
    else:
        if not st["id"]:
            card = _card("READY", "Add audio, pick who speaks, then press Listen.", "")
        elif st["stopped"]:
            card = _card("STOPPED", "Stopped", "Nothing was saved. Your inputs are still here.", None, "#b45309")
        elif st["error"]:
            card = _card("PROBLEM", "Something went wrong", st["error"], None, "#b91c1c")
        elif st["kind"] == "listening":
            card = _card("STEP 1 DONE", "Check who says what", "Fix the 'Who' column if needed, then press "
                         "Preview or Make video.")
        else:
            r = st["result"]
            card = _card("DONE", "Preview ready" if st["kind"] == "preview" else "Video ready",
                         "" if st["kind"] == "preview" else f"Saved in the videos folder as <b>{r.name}</b>", 100)
        if st["id"] and seen != st["id"]:
            seen = st["id"]
            live = gr.update(visible=False)
            if st["error"] is None and st["result"] is not None:
                if st["kind"] == "listening":
                    table = st["result"]
                else:
                    video = str(st["result"])
    btn = gr.update(interactive=not running)
    return card, log, table, video, live, btn, btn, btn, gr.update(visible=running), seen, live_m


def restore():
    """Brings back everything entered before a reload."""
    d = jobs.load_draft()
    n = cast.names()
    audio = d.get("audio") if d.get("audio") and Path(d["audio"]).exists() else None
    pick = lambda k: [x for x in (d.get(k) or []) if x in n]
    st = jobs.status()
    seen = st["id"] if not st["running"] else -1
    video = d.get("video") if d.get("video") and Path(d["video"]).exists() else None
    return (audio, gr.update(choices=n, value=pick("speaking")), gr.update(choices=n, value=pick("silent")),
            d.get("locs") or ["Auto"], d.get("notes", ""), d.get("title", ""), d.get("ratio") or RATIOS[0],
            d.get("lang") or "Auto-detect", d.get("subs", True), d.get("table") or None, video, seen)


# ---------------------------------------------------------------- Characters
FIELDS = ["name", "body", "head", "skin", "eyes", "hair", "hair_color", "top", "bottom", "bottom_color", "extras",
          "height", "width"]


def _spec(*vals):
    return dict(zip(FIELDS, vals))


def live_preview(*vals):
    return toon.sheet(_spec(*vals), cell=300)


def _cast_gallery():
    out = []
    for c in cast.list_characters():
        p = cast.CHARACTERS / c["id"] / "preview.png"
        if p.exists():
            out.append((str(p), f'{c["name"]} (v{c["version"]})'))
    return out


def _refresh_names():
    n = cast.names()
    return gr.update(choices=n), gr.update(choices=n), gr.update(choices=n)


def save_char(*vals, as_new=False):
    spec = _spec(*vals)
    if not (spec["name"] or "").strip():
        return ("Give the character a name first.", gr.update(), gr.update(), gr.update(), gr.update())
    cid, v = cast.save(spec, as_new=as_new)
    msg = (f"Saved **{spec['name']}** (version {v}). It's now in your cast — pick it in any video."
           if v == 1 else f"Updated **{spec['name']}** to version {v} (earlier versions are kept).")
    return (msg, _cast_gallery(), *_refresh_names())


def save_new(*vals):
    return save_char(*vals, as_new=True)


def open_char(name):
    c = cast.by_name(name) if name else None
    if not c:
        return [gr.update()] * len(FIELDS)
    d = {**toon.DEFAULT, **c}
    return [d[f] for f in FIELDS]


def export_char(name):
    c = cast.by_name(name) if name else None
    if not c:
        return None, "Open a saved character first."
    return str(cast.export(c["id"])), f"Exported **{name}** — keep this file as a backup or copy it to another Mac."


def import_char(path):
    if not path:
        return "Choose a character file.", gr.update(), gr.update(), gr.update(), gr.update()
    c = cast.import_file(path)
    return (f"Imported **{c['name']}**.", _cast_gallery(), *_refresh_names())


# ---------------------------------------------------------------- Props & places
def _prop_gallery():
    out = []
    PV = WORK / "props"
    PV.mkdir(parents=True, exist_ok=True)
    for name, (layer, fn, words) in props.PROPS.items():
        f = PV / f"{cast.slug(name)}.png"
        if not f.exists():
            S = 220
            surf = skia.Surface.MakeRaster(skia.ImageInfo.Make(S, S, skia.kRGBA_8888_ColorType,
                                                               skia.kPremul_AlphaType))
            cv = surf.getCanvas()
            cv.clear(skia.ColorSetARGB(255, 240, 242, 246))
            try:
                if layer == "front":
                    props.draw_front(cv, name, S / 2, S * 0.95, S * 1.2, 0.7, 0.4,
                                     **({"laptops": [0.0]} if name == "desk" else {}))
                elif layer == "hand":
                    cv.save()
                    cv.translate(S / 2, S * 0.62)
                    cv.scale(S * 2.2, S * 2.2)
                    fn(cv, 0.011)
                    cv.restore()
                elif layer == "worn":
                    cv.save()
                    cv.translate(S / 2, S * 0.6)
                    cv.scale(S * 1.6, S * 1.6)
                    if name.startswith("necklace"):
                        fn(cv, (0, -0.02), 0.011)
                    else:
                        fn(cv, 0.12, 0.011)
                    cv.restore()
                else:
                    big = name in ("fridge", "door", "bookshelf", "whiteboard")
                    props.draw(cv, name, S / 2, S * 0.95 if not name == "whiteboard" else S * 1.25,
                               S * (0.75 if big else 1.2))
            except Exception:
                traceback.print_exc()
            Image.fromarray(surf.makeImageSnapshot().toarray()[..., :3].copy()).save(f)
        out.append((str(f), f"{name} · {layer}"))
    for name, m in props.uploaded().items():
        out.append((m["path"], f"{name} · {m['layer']} (yours)"))
    return out


def add_prop(name, img, layer, words, size):
    if not img:
        return "Add a PNG image (transparent background works best).", gr.update()
    n = props.add_prop(name, img, layer, words, size)
    return f"Added prop **{n}**. It appears when someone says: {words or '(no words yet)'}", _prop_gallery()


def add_loc(name, image):
    if not image:
        return "Add an image.", gr.update(), gr.update()
    n = backgrounds.add_location(name or "My place", image)
    return f"Added location **{n}**.", gr.update(choices=["Auto"] + backgrounds.list_locations()), _loc_gallery()


def _loc_gallery():
    return [(backgrounds.preview(n), n) for n in backgrounds.list_locations()]


MOTION = {"Held poses — snaps between poses, cuts to whoever speaks (cartoon-shorts style)": "held",
          "Smooth — everything moves gently all the time (older style)": "smooth"}


def save_set(key, model, whisper, fps, motion):
    s = load_settings()
    s.update({"claude_api_key": key.strip(), "claude_model": model.strip() or "claude-sonnet-5-5",
              "whisper_model": whisper, "fps": int(fps), "motion": MOTION.get(motion, "held")})
    save_settings(s)
    return "Settings saved."


def _status():
    rh = "✅ installed" if lipsync.rhubarb_path() else "not installed — using built-in lip-sync"
    try:
        import faster_whisper  # noqa
        st = "✅ installed"
    except Exception:
        st = "not installed — speech found by loudness only (no words)"
    return f"- Speech-to-text: {st}\n- Rhubarb lip-sync: {rh}\n- Videos folder: `{VIDEOS}`"


# ---------------------------------------------------------------- page
def build():
    s = load_settings()
    names = cast.names()
    d = toon.DEFAULT
    with gr.Blocks(title="Toonbox") as ui:
        gr.Markdown("# Toonbox\nAudio + your saved characters → cartoon video. Runs on this Mac. "
                    "Made by Harshad.", elem_id="title")
        with gr.Tab("🎬 New video"):
            with gr.Row():
                with gr.Column(scale=5):
                    audio = gr.Audio(label="Audio (dialogue / story)", type="filepath", sources=["upload"])
                    speaking = gr.Dropdown(names, multiselect=True, label="Who speaks",
                                           info="Pick from your cast. First time: pick them in the order they "
                                                "first speak — after that the app knows their voices.")
                    silent = gr.Dropdown(names, multiselect=True, label="Also on screen (doesn't speak)")
                    locs = gr.Dropdown(["Auto"] + backgrounds.list_locations(), value=["Auto"], multiselect=True,
                                       label="Location", info="Auto = picked from the audio and notes. "
                                                              "Pick more than one for scene changes (in order).")
                    notes = gr.Textbox(label="Scene / story notes (optional)", lines=3,
                                       placeholder="e.g. A couple having a conversation in their bedroom. "
                                                   "She is on the phone. They sit on the sofa.")
                    title = gr.Textbox(label="Title on top (optional)")
                    ratio = gr.Radio(RATIOS, value=RATIOS[0], label="Aspect ratio")
                    with gr.Accordion("More options", open=False):
                        lang = gr.Dropdown(list(pipeline.LANGS), value="Auto-detect", label="Language of the audio")
                        subs = gr.Checkbox(True, label="Show captions")
                    listen = gr.Button("1 · Listen to audio", elem_classes="step-btn")
                with gr.Column(scale=6):
                    card = gr.HTML(_card("READY", "Add audio, pick who speaks, then press Listen.", ""))
                    with gr.Row():
                        prev = gr.Button("Preview first 15 s", elem_classes="step-btn")
                        make = gr.Button("2 · Make video", variant="primary", elem_classes="step-btn")
                        stop = gr.Button("⏹ Stop", variant="stop", elem_classes="step-btn", visible=False)
                    livev = gr.Image(label="Live view (updates while drawing)", interactive=False, height=420,
                                     visible=False)
                    video = gr.Video(label="Your video", height=520)
                    table = gr.Dataframe(headers=["Start", "End", "Who", "Words", "Loudness"],
                                         datatype=["str", "str", "str", "str", "number"], interactive=True,
                                         label="Who says what — edit 'Who' or 'Words' if needed", wrap=True)
                    with gr.Accordion("Details (log)", open=False):
                        log = gr.Textbox(show_label=False, lines=8, interactive=False)
            seen = gr.State(-1)
            live_m = gr.State(0.0)
            ok = gr.Checkbox(visible=False)
            vin = [audio, speaking, silent, locs, notes, title, ratio, lang, subs, table]
            listen.click(do_listen, [audio, speaking, lang], log)
            make.click(do_make, vin, log)
            prev.click(do_preview, vin, log)
            stop.click(do_stop, ok, log, js="(x) => confirm('Stop now? What has been drawn so far is thrown away. "
                                             "Your inputs stay.')")
            gr.Timer(1.0).tick(tick, [seen, live_m], [card, log, table, video, livev, listen, prev, make, stop, seen,
                                                      live_m])
            # save a draft whenever something changes, so a reload or sleep loses nothing
            audio.upload(lambda a: jobs.save_draft(audio=a, table=None, video=None) and None, audio, None)
            audio.clear(lambda: jobs.save_draft(audio="", table=None) and None, None, None)
            for comp, key in ((speaking, "speaking"), (silent, "silent"), (locs, "locs"), (notes, "notes"),
                              (title, "title"), (ratio, "ratio"), (lang, "lang"), (subs, "subs")):
                comp.change(lambda v, k=key: jobs.save_draft(**{k: v}) and None, comp, None)
            table.input(lambda t: jobs.save_draft(table=_rows(t)) and None, table, None)
            ui.load(restore, None, [audio, speaking, silent, locs, notes, title, ratio, lang, subs, table, video,
                                    seen])

        with gr.Tab("🧍 Characters"):
            gr.Markdown("Create a character once, save it, and reuse it in every episode — it looks exactly the "
                        "same each time. Saving again with the same name makes a new version (old ones are kept).")
            with gr.Row():
                with gr.Column(scale=4):
                    openc = gr.Dropdown(names, label="Open a saved character", value=None)
                    cname = gr.Textbox(d["name"], label="Name")
                    body = gr.Radio(list(toon.BODY_STYLES), value=d["body"], label="Body style")
                    head = gr.Radio(toon.HEADS, value=d["head"], label="Head shape")
                    with gr.Row():
                        skin = gr.ColorPicker(d["skin"], label="Skin / body colour")
                        hairc = gr.ColorPicker(d["hair_color"], label="Hair colour")
                    hair = gr.Dropdown(toon.HAIRS, value=d["hair"], label="Hair")
                    eyes = gr.Radio(toon.EYES, value=d["eyes"], label="Eyes")
                    with gr.Row():
                        top = gr.ColorPicker(d["top"], label="Top colour")
                        botc = gr.ColorPicker(d["bottom_color"], label="Bottom colour")
                    bottom = gr.Radio(toon.BOTTOMS, value=d["bottom"], label="Bottom")
                    extras = gr.CheckboxGroup(toon.EXTRAS, value=[], label="Extras")
                    with gr.Row():
                        height = gr.Slider(0.6, 1.2, d["height"], step=0.05, label="Height (0.7 = child)")
                        width = gr.Slider(0.8, 1.3, d["width"], step=0.05, label="Build")
                    with gr.Row():
                        csave = gr.Button("Save", variant="primary")
                        cnew = gr.Button("Save as a new character")
                    cmsg = gr.Markdown()
                with gr.Column(scale=6):
                    sheet = gr.Image(toon.sheet(d, cell=300), label="Preview (a few expressions)",
                                     interactive=False, height=520)
                    gal = gr.Gallery(_cast_gallery(), label="Your cast", columns=4, height=260)
                    with gr.Accordion("Backup / move characters", open=False):
                        with gr.Row():
                            cexp = gr.Button("Export the open character")
                            cfile = gr.File(label="Exported file")
                        cimp = gr.File(label="Import a character file (.toonchar.json)", type="filepath")
            cin = [cname, body, head, skin, eyes, hair, hairc, top, bottom, botc, extras, height, width]
            for c in cin:
                (c.release if isinstance(c, gr.Slider) else c.change)(live_preview, cin, sheet)
            csave.click(save_char, cin, [cmsg, gal, speaking, silent, openc])
            cnew.click(save_new, cin, [cmsg, gal, speaking, silent, openc])
            openc.change(open_char, openc, cin)
            cexp.click(export_char, openc, [cfile, cmsg])
            cimp.upload(import_char, cimp, [cmsg, gal, speaking, silent, openc])

        with gr.Tab("🪑 Props & places"):
            gr.Markdown("Props come in by themselves when the dialogue or your notes mention them "
                        "(say *laptop* → desk with laptops, *call* → phone in hand, *dog* → a dog walks in). "
                        "Add your own as PNG images.")
            with gr.Row():
                with gr.Column(scale=4):
                    pname = gr.Textbox(label="Prop name", placeholder="Cricket bat")
                    pimg = gr.Image(label="Prop image (PNG, transparent background)", type="filepath",
                                    sources=["upload"], height=220)
                    player = gr.Radio(["floor", "back", "hand", "front"], value="floor", label="Where it goes",
                                      info="floor = next to characters · back = behind · hand = held · front = "
                                           "in front (like a table)")
                    pwords = gr.Textbox(label="Words that bring it in (comma separated)",
                                        placeholder="bat, cricket, match")
                    psize = gr.Slider(0.05, 1.2, 0.3, step=0.05, label="Size (1 = as tall as a character)")
                    padd = gr.Button("Add prop", variant="primary")
                    pmsg = gr.Markdown()
                    gr.Markdown("---")
                    lname = gr.Textbox(label="New location name", placeholder="Dadi's house")
                    limg = gr.Image(label="Background image", type="filepath", sources=["upload"], height=200)
                    ladd = gr.Button("Add location")
                    lmsg = gr.Markdown()
                with gr.Column(scale=6):
                    pgal = gr.Gallery(_prop_gallery(), label="Props", columns=5, height=420)
                    lgal = gr.Gallery(_loc_gallery(), label="Locations", columns=4, height=300)
            padd.click(add_prop, [pname, pimg, player, pwords, psize], [pmsg, pgal])
            ladd.click(add_loc, [lname, limg], [lmsg, locs, lgal])

        with gr.Tab("⚙️ Settings"):
            gr.Markdown("**Smart director (optional).** Without a key, the built-in director plans everything from "
                        "the words, loudness and pauses — free. With a Claude API key it also understands the meaning "
                        "of the dialogue and your notes (a few paise per video).")
            key = gr.Textbox(s.get("claude_api_key", ""), label="Claude API key", type="password")
            model = gr.Textbox(s.get("claude_model", "claude-sonnet-5-5"), label="Model")
            whisper = gr.Dropdown(["large-v3-turbo", "medium", "small"], value=s.get("whisper_model"),
                                  label="Speech-to-text model", info="large-v3-turbo = best for Hindi; small = fastest")
            fps = gr.Radio([12, 24, 30], value=s.get("fps", 24), label="Frames per second")
            motion = gr.Radio(list(MOTION), value=next((k for k, v in MOTION.items() if v == s.get("motion", "held")),
                                                        list(MOTION)[0]), label="Motion style")
            ssave = gr.Button("Save settings", variant="primary")
            smsg = gr.Markdown()
            gr.Markdown(_status())
            ssave.click(save_set, [key, model, whisper, fps, motion], smsg)

        ui.load(lambda: (gr.update(choices=cast.names()), _cast_gallery()), None, [openc, gal])
    return ui


def main():
    build().launch(inbrowser=True, theme=THEME, css=CSS, allowed_paths=[str(ROOT), str(DATA)], server_name="127.0.0.1")


if __name__ == "__main__":
    main()
