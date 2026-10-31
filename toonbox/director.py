"""The director: reads the lines (words, who, loudness, pitch, pauses) and plans the whole video —
locations, props, expressions, gestures, listener reactions, emotes and camera shots.

Built-in rules work offline for free. With a Claude API key in Settings, a smarter director reads the meaning
of the dialogue and the story notes and picks from the same menus (costs a few paise per video).
"""
import json
import random
import re

from . import props as P

EMOTIONS = ["neutral", "happy", "laugh", "angry", "shocked", "sad", "tired", "unimpressed", "smug", "suspicious",
            "confused", "scared", "love", "awkward", "thinking"]
GESTURES = ["none", "talk", "point", "open_palm", "shrug", "hands_up", "cheer", "calm", "cross_arms", "hips",
            "self", "clasp", "facepalm", "chin", "wave", "beckon", "fists", "head_hold", "cover_mouth", "phone"]
BODY = ["none", "nod", "shake", "jump", "bounce", "flinch", "slump", "lean_in", "lean_back", "stomp"]
EMOTES = ["!", "?", "anger", "sweat", "sparkle", "think", "heart", "shock"]
LOCATION_WORDS = [
    ("Office", r"\b(office|boss|meeting|email|laptop|computer|work|deadline|manager|client|salary)\b"),
    ("Kitchen", r"\b(kitchen|cook|cooking|khana|chai|tea|breakfast|dinner|fridge|roti)\b"),
    ("Bedroom", r"\b(bed|sleep|sleeping|bedroom|wake up|neend|alarm)\b"),
    ("Classroom", r"\b(class|school|teacher|exam|homework|student|ma'am|sir)\b"),
    ("Park", r"\b(park|garden|walk|jogging|picnic)\b"),
    ("Street", r"\b(road|street|car|bike|traffic|auto|taxi|bus)\b"),
]

W = lambda *ws: r"(?<![\w'])(" + "|".join(ws) + r")(?![\w'])"
RX = {
    "laugh": W("haha+", "hahaha", "lol", "lmao", "hehe+", "हाहा", "हा हा"),
    "angry": W("how dare", "shut up", "get out", "stop it", "idiot", "stupid", "nonsense", "what the hell",
               "seriously", "bakwas", "chup", "pagal", "gussa", "बकवास", "चुप", "पागल", "गुस्सा", "बस करो"),
    "shocked": W("what", "wow", "oh my god", "omg", "oh no", "no way", "really", "are you serious", "kya",
                 "kya baat", "hai ram", "क्या", "सच में", "हे भगवान"),
    "sad": W("sorry", "please", "miss you", "i'm sad", "maaf", "plz", "sorry yaar", "माफ", "सॉरी", "प्लीज"),
    "scared": W("help", "scary", "scared", "afraid", "dar", "bhoot", "डर", "बचाओ"),
    "happy": W("thank you", "thanks", "great", "awesome", "amazing", "love it", "yay", "nice", "cool", "yes",
               "yeah", "wah", "waah", "badhiya", "mast", "shabash", "वाह", "बढ़िया", "मस्त", "धन्यवाद"),
    "love": W("love you", "i love", "miss you", "darling", "jaan", "baby", "pyaar", "प्यार"),
    "tired": W("tired", "sleepy", "exhausted", "bored", "thak", "थक"),
    "unimpressed": W("fine", "alright", "whatever", "okay fine", "ok fine", "theek hai", "ठीक है"),
    "awkward": W("i'm just saying", "just saying", "i don't know", "umm+", "uh+", "pata nahi", "पता नहीं"),
    "thinking": W("hmm+", "let me think", "maybe", "shayad", "soch", "hmm", "शायद", "सोच"),
    "suspicious": W("who", "huh", "kaun", "कौन", "who else", "really now"),
    "smug": W("told you", "i know", "obviously", "of course", "maine kaha tha"),
}
CUE = {
    "you": W("you", "your", "you're", "tum", "tu", "aap", "tera", "tumhara", "tumne", "tune", "तुम", "आप", "तू",
             "तुमने"),
    "me": W("i", "i'm", "me", "my", "mine", "main", "mujhe", "mera", "meri", "मैं", "मुझे", "मेरा", "मेरी"),
    "calm": W("look", "listen", "wait", "hold on", "relax", "calm down", "dekho", "suno", "ruko", "देखो", "सुनो",
              "रुको", "ok look"),
    "wave": W("hey", "hi", "hello", "bye", "namaste", "goodbye", "नमस्ते"),
    "beckon": W("come", "come on", "come here", "aao", "idhar", "chalo", "आओ", "इधर", "चलो"),
    "no": W("no", "nope", "never", "nahi", "nahin", "नहीं", "nobody"),
    "yes": W("yes", "yeah", "yep", "ok", "okay", "haan", "ha", "हाँ", "हां"),
    "why": W("what do you mean", "why", "how", "kyun", "kyon", "kaise", "क्यों", "कैसे"),
    "stop": W("stop", "enough", "bas", "बस"),
    "omg": W("oh no", "oh my god", "omg", "hai ram", "हे भगवान"),
}
OFF = re.compile(r"(took it off|take it off|taking it off|removed|remove it|utaar|उतार)")


def _has(rx, t):
    return re.search(rx, t) is not None


def classify(text, loud, pz):
    if not (text or "").strip():  # no words available: act from the voice alone
        if loud > 0.9 or pz > 1.3:
            return "happy", 1
        if loud < -0.9:
            return "unimpressed", 0
        return "neutral", 0
    t = (text or "").lower()
    raw = text or ""
    caps = len(re.findall(r"\b[A-Z]{2,}\b", raw))
    exclaim, ques = raw.count("!"), raw.count("?")
    hot = loud > 1.0 or pz > 1.2
    if _has(RX["laugh"], t):
        return "laugh", 2
    if _has(RX["angry"], t) or (caps and (exclaim or ques)) or (hot and exclaim and caps):
        return "angry", 2 if caps or hot else 1
    if _has(RX["love"], t):
        return "love", 1
    if _has(RX["scared"], t):
        return "scared", 1
    if _has(RX["sad"], t):
        return "sad", 1
    if ques >= 2 and _has(RX["suspicious"], t):
        return "suspicious", 2
    if (_has(RX["shocked"], t) and (exclaim or ques)) or (exclaim and len(t.split()) <= 2 and hot):
        return "shocked", 2 if hot or exclaim else 1
    if ques >= 2 or (_has(RX["suspicious"], t) and ques):
        return "suspicious", 1
    if _has(RX["tired"], t):
        return "tired", 1
    if _has(RX["unimpressed"], t):
        return "unimpressed", 1
    if _has(RX["awkward"], t):
        return "awkward", 1
    if _has(RX["thinking"], t):
        return "thinking", 1
    if _has(RX["smug"], t):
        return "smug", 1
    if _has(RX["happy"], t) or (exclaim and not hot):
        return "happy", 1
    if ques:
        return "confused", 1
    if hot:
        return "shocked" if exclaim else "angry", 1
    return "neutral", 0


def pick_gesture(emo, inten, text, dur, rnd):
    t = (text or "").lower()
    if _has(CUE["omg"], t):
        return "head_hold"
    if _has(CUE["stop"], t):
        return "calm"
    if _has(CUE["calm"], t):
        return "calm"
    if _has(CUE["wave"], t) and dur < 1.6:
        return "wave"
    if _has(CUE["beckon"], t):
        return "beckon"
    if emo == "suspicious":
        return "point" if _has(CUE["you"], t) or inten > 1 else "cross_arms"
    if emo == "angry":
        return "point" if _has(CUE["you"], t) else rnd.choice(["fists", "hips"])
    if emo == "shocked":
        return "hands_up" if inten > 1 else "cover_mouth"
    if emo == "sad":
        return "clasp" if "sorry" in t or "please" in t or "माफ" in t else "none"
    if emo == "scared":
        return "head_hold"
    if emo == "laugh":
        return "cheer" if rnd.random() < 0.3 else "none"
    if emo == "happy":
        return "cheer" if "!" in (text or "") and inten > 1 else ("open_palm" if dur > 1.4 else "none")
    if emo == "thinking":
        return "chin"
    if emo == "unimpressed":
        return "hips" if rnd.random() < 0.5 else "cross_arms"
    if emo == "awkward":
        return "self" if _has(CUE["me"], t) else "shrug"
    if emo == "confused":
        return "shrug" if _has(CUE["why"], t) else "open_palm"
    if emo == "smug":
        return "self"
    if _has(CUE["why"], t):
        return "shrug"
    if dur > 1.8:
        return "talk"
    return "none"


def pick_body(emo, inten, text):
    t = (text or "").lower()
    if emo == "angry" and inten > 1:
        return "stomp" if "!" in (text or "") else "lean_in"
    if emo in ("shocked", "scared") and inten > 1:
        return "jump"
    if emo == "laugh":
        return "bounce"
    if emo == "sad":
        return "slump"
    if emo == "suspicious":
        return "lean_in"
    if _has(CUE["no"], t) and len(t.split()) <= 4:
        return "shake"
    if _has(CUE["yes"], t) and len(t.split()) <= 4:
        return "nod"
    return "none"


REACT = {"angry": ("scared", "flinch", "sweat"), "shocked": ("confused", "none", "?"),
         "sad": ("unimpressed", "none", None), "laugh": ("happy", "bounce", None), "happy": ("happy", "nod", None),
         "suspicious": ("awkward", "lean_back", "sweat"), "confused": ("thinking", "none", None),
         "love": ("love", "none", "heart"), "scared": ("scared", "flinch", None),
         "unimpressed": ("sad", "none", None), "awkward": ("unimpressed", "none", None),
         "thinking": ("neutral", "none", None), "smug": ("unimpressed", "none", None), "tired": ("tired", "none", None),
         "neutral": ("neutral", "nod", None)}
EMOTE_FOR = {"angry": "anger", "shocked": "!", "suspicious": "?", "confused": "?", "love": "heart",
             "scared": "sweat", "awkward": "sweat", "laugh": "sparkle", "thinking": "think"}


# ------------------------------------------------------------------ scenes, locations, props
def auto_location(text):
    t = text.lower()
    for name, rx in LOCATION_WORDS:
        if re.search(rx, t):
            return name
    return "Living room"


def split_scenes(lines, locations, duration):
    if len(locations) <= 1 or len(lines) < 2:
        return [{"start": 0.0, "end": duration, "location": locations[0]}]
    gaps = sorted(range(1, len(lines)), key=lambda i: lines[i]["start"] - lines[i - 1]["end"], reverse=True)
    cuts = sorted(gaps[: len(locations) - 1])
    scenes, start = [], 0.0
    for n, i in enumerate(cuts + [len(lines)]):
        end = duration if i == len(lines) else (lines[i - 1]["end"] + lines[i]["start"]) / 2
        scenes.append({"start": round(start, 2), "end": round(end, 2), "location": locations[n]})
        start = end
    return scenes


def _mentions(text):
    """Props mentioned in a piece of text (longest phrases first)."""
    t = " " + (text or "").lower() + " "
    found = []
    for w, names in sorted(P.keywords().items(), key=lambda kv: -len(kv[0])):
        if re.search(r"(?<![\w])" + re.escape(w) + r"(?![\w])", t):
            for n in names:
                if n not in found:
                    found.append(n)
    return found


def plan_props(scene, lines, cast, notes, rnd):
    kit = P.LOCATION_KIT.get(scene["location"], {})
    sl = [l for l in lines if scene["start"] <= l["start"] < scene["end"]]
    alltext = " ".join(l.get("text", "") for l in sl) + " " + (notes or "")
    ment = _mentions(alltext)
    front = kit.get("front")
    for n in ment:
        if P.layer_of(n) == "front" and front is None:
            front = n
    back = list(kit.get("back", []))
    for n in ment:
        if P.layer_of(n) == "back" and n not in back and len(back) < 3:
            back.append(n)
    sit = bool(re.search(r"\b(sit|sitting|seated|baithe|baith|बैठ)", (notes or "").lower())) or \
        any(b in ("sofa", "bed") for b in back if b in _mentions(notes or ""))
    if sit and not any(b in ("sofa", "chair", "office chair", "bed") for b in back):
        back.append("office chair" if front == "desk" else "sofa")
    scene["front"] = front
    scene["desk_items"] = kit.get("desk_items", "laptops" if front == "desk" and "laptop" in alltext.lower()
                                  or "computer" in alltext.lower() else "none")
    scene["back"] = back
    scene["sit"] = sit
    # things that appear when mentioned
    floor, hands, worn = [], [], []
    seen = set()
    for l in sl:
        for n in _mentions(l.get("text", "")):
            layer = P.layer_of(n)
            if layer == "floor" and n not in seen:
                seen.add(n)
                animal = n in ("dog", "cat")
                floor.append({"name": n, "t0": max(scene["start"], l["start"] - (1.6 if animal else 0.2)),
                              "t1": scene["end"], "near": l["speaker"], "enter": animal})
            elif layer == "hand" and n != "necklace":
                hands.append({"char": l["speaker"], "name": n, "t0": l["start"] - 0.35, "t1": l["end"] + 1.2})
            elif layer == "worn" and ("worn", n) not in seen:
                seen.add(("worn", n))
                owner = l["speaker"] if re.search(r"\b(my|mera|meri)\b", l.get("text", "").lower()) else \
                    next((c for c in cast if c != l["speaker"]), l["speaker"])
                worn.append({"char": owner, "name": n, "t0": scene["start"], "t1": scene["end"]})
        if OFF.search((l.get("text") or "").lower()):
            for w in worn:
                if w["t1"] > l["start"]:
                    w["t1"] = min(w["t1"], max(w["t0"], l["start"] - 1.5))
    # notes can bring props into the whole scene ("she is on the phone", "he has a cup of tea")
    for n in _mentions(notes or ""):
        if P.layer_of(n) == "hand" and n != "necklace":
            who = cast[0]
            for c in cast:
                if re.search(re.escape(c.lower()), (notes or "").lower()):
                    who = c
                    break
            hands.append({"char": who, "name": n, "t0": scene["start"], "t1": scene["end"], "idle": True})
        elif P.layer_of(n) == "floor" and n not in seen:
            seen.add(n)
            floor.append({"name": n, "t0": scene["start"], "t1": scene["end"], "near": None, "enter": False})
    scene["floor"], scene["hands"], scene["worn"] = floor, hands, worn
    return scene


# ------------------------------------------------------------------ the plan
def rule_plan(lines, cast, locations, notes, duration, seed=1, overrides=None):
    rnd = random.Random(seed)
    if not locations or locations == ["Auto"]:
        locations = [auto_location(" ".join(l.get("text", "") for l in lines) + " " + (notes or ""))]
    scenes = [plan_props(s, lines, cast, notes, rnd) for s in split_scenes(lines, locations, duration)]
    acts, emotes, shots = [], [], []
    overrides = overrides or {}
    since_wide = 0
    prev_focus = None
    for i, l in enumerate(lines):
        sp = l["speaker"]
        d = l["end"] - l["start"]
        text = l.get("text") or ""
        o = overrides.get(i, {})
        emo, inten = classify(text, l.get("loud", 0.0), l.get("pz", 0.0))
        emo = o.get("emotion") if o.get("emotion") in EMOTIONS else emo
        inten = max(inten, int(o.get("intensity", 0) or 0))
        g = o.get("gesture") if o.get("gesture") in GESTURES else pick_gesture(emo, inten, text, d, rnd)
        b = o.get("body") if o.get("body") in BODY else pick_body(emo, inten, text)
        l["emotion"], l["gesture"] = emo, g
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        hold_to = (nxt["start"] if nxt else duration) if (nxt and nxt["speaker"] == sp) else l["end"] + 0.6
        acts.append({"char": sp, "t0": l["start"] - 0.12, "t1": max(hold_to, l["end"] + 0.3), "expr": emo})
        if g != "none":
            g_end = l["end"] + (0.25 if g in ("talk", "wave", "beckon") else 0.45)
            acts.append({"char": sp, "t0": l["start"] + min(0.12, d * 0.15), "t1": g_end, "gesture": g})
        if b != "none":
            acts.append({"char": sp, "t0": l["start"] + 0.05, "t1": l["start"] + (max(0.9, d) if b in
                                                                                 ("slump", "lean_in", "lean_back")
                                                                                 else 0.7), "body": b})
        em = o.get("emote") if o.get("emote") in EMOTES else (EMOTE_FOR.get(emo) if inten > 1 or
                                                             (emo in ("thinking", "love") and rnd.random() < .6)
                                                             else None)
        if em:
            emotes.append({"char": sp, "t": l["start"] + min(0.3, d * 0.3), "dur": 1.3, "name": em})
        # listeners
        others = [c for c in cast if c != sp]
        for c in others:
            rexp, rbody, remo = REACT.get(emo, REACT["neutral"])
            if o.get("listener_emotion") in EMOTIONS:
                rexp = o["listener_emotion"]
            t0 = l["start"] + 0.35
            t1 = (nxt["start"] if nxt and nxt["speaker"] != c else l["end"] + 1.0) + 0.1
            if rexp != "neutral" or inten:
                acts.append({"char": c, "t0": t0, "t1": max(t1, t0 + 0.6), "expr": rexp})
            if rbody != "none" and (inten or rnd.random() < 0.35):
                acts.append({"char": c, "t0": t0, "t1": t0 + 0.6, "body": rbody})
            if remo and inten > 1 and rnd.random() < 0.7:
                emotes.append({"char": c, "t": t0 + 0.2, "dur": 1.2, "name": remo})
            if emo in ("thinking", "confused") and d > 1.5 and rnd.random() < 0.4:
                acts.append({"char": c, "t0": t0, "t1": l["end"] + 0.5, "gesture": "chin"})
        # camera
        scene_start = any(abs(s["start"] - l["start"]) < 0.01 or (i > 0 and lines[i - 1]["end"] <= s["start"] <=
                                                                  l["start"]) for s in scenes) or i == 0
        cam = o.get("camera")
        if cam not in ("wide", "close"):
            if scene_start:
                cam = "wide"
            elif inten > 1 or l.get("loud", 0) > 1.1:
                cam = "close"
            elif d < 0.9 and shots:
                cam = None  # keep the current shot
            elif since_wide >= 3:
                cam = "wide"
            elif sp != prev_focus and d > 1.5:
                cam = "close"
            else:
                cam = "wide" if rnd.random() < 0.45 else "close"
        if cam:
            shake = bool(re.search(r"\b[A-Z]{3,}\b", text)) or l.get("loud", 0) > 1.5
            shots.append({"start": max(0.0, l["start"] - 0.1) if i else 0.0, "kind": cam,
                          "focus": sp if cam == "close" else None, "push": 0.08 if inten > 1 else 0.03,
                          "shake": (l["start"], l["start"] + 0.45) if shake and inten > 1 else None})
            since_wide = 0 if cam == "wide" else since_wide + 1
            prev_focus = sp if cam == "close" else None
        # reaction shot in a pause after a strong line
        gap = (nxt["start"] if nxt else duration) - l["end"]
        if others and gap > 0.9 and (inten > 1 or "?" in text):
            c = others[0] if len(others) == 1 else (nxt["speaker"] if nxt and nxt["speaker"] != sp else others[0])
            shots.append({"start": l["end"] + 0.15, "kind": "close", "focus": c, "push": 0.04, "shake": None})
            prev_focus = c
            since_wide += 1
    return _finish({"scenes": scenes, "shots": shots, "acts": acts, "emotes": emotes}, duration)


# ------------------------------------------------------------------ held-pose camera (cut-based storytelling)
# Words that mean the characters do something TOGETHER, so both must be in the frame.
TOGETHER = re.compile(W("hug", "hugs", "hugging", "kiss", "fight", "fighting", "push", "pushed", "slap", "slapped", "hit",
                        "punch", "hold my hand", "hold hands", "dance", "dancing", "massage", "give", "gave", "take this",
                        "here you go", "here,? take", "catch", "together", "both of us", "come here", "high five",
                        "hand me", "pass me", "let's go", "lets go", "chalo", "pakdo", "lo", "le lo", "do mujhe",
                        "gale", "maar", "mara", "dhakka", "saath", "dono"), re.I)


def _together(text):
    return bool(TOGETHER.search(text or ""))


def held_shots(plan, lines, cast, notes, duration, overrides=None):
    """Camera for the held-pose style, like Indian cartoon shorts:
    - an opening wide shot (everyone in frame) to set the scene,
    - then mostly single-character close-ups that CUT to whoever is speaking,
    - silent reaction cutaways to the listener in pauses and in the middle of long lines,
    - a wide two-shot whenever the characters do something together (hug, give, fight, come here…),
      when an animal/prop walks in, when both move at once, or to re-establish after many close-ups.
    Every shot has a slow push-in so held drawings never look frozen."""
    overrides = overrides or {}
    shots = [{"start": 0.0, "kind": "wide", "focus": None, "push": 0.05, "shake": None}]
    scene_starts = [s["start"] for s in plan["scenes"][1:]]
    entries = [f["t0"] for s in plan["scenes"] for f in s.get("floor", []) if f.get("enter")]
    closes = 0
    for i, l in enumerate(lines):
        sp, d, text = l["speaker"], l["end"] - l["start"], l.get("text") or ""
        o = overrides.get(i, {})
        others = [c for c in cast if c != sp]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        t0 = max(0.0, l["start"] - 0.08)  # cut just before the first word, like an editor would
        strong = l.get("loud", 0) > 1.1 or "!" in text
        shake = (l["start"], l["start"] + 0.4) if (bool(re.search(r"\b[A-Z]{3,}\b", text)) or l.get("loud", 0) > 1.5) \
            else None
        new_scene = any(l["start"] - 1.0 <= s <= l["start"] + 0.1 for s in scene_starts)
        animal = any(l["start"] - 1.8 <= e <= l["end"] for e in entries)
        cam = o.get("camera") if o.get("camera") in ("wide", "close") else None
        if cam is None:
            if not others or new_scene or _together(text) or animal or closes >= 6:
                cam = "wide"
            elif i == 0 and l["start"] < 1.2 and d < 2.5:
                cam = "wide"  # let the opening wide shot breathe for the first short line
            else:
                cam = "close"
        if i == 0 and cam == "wide":
            shots[0]["shake"] = shake
        else:
            shots.append({"start": t0, "kind": cam, "focus": sp if cam == "close" else None,
                          "push": 0.07 if strong else 0.05, "shake": shake, "line": True})
        closes = closes + 1 if cam == "close" else 0
        # the listener = whoever this line answers (last different speaker), not just the first other character
        prev_sp = next((lines[j]["speaker"] for j in range(i - 1, -1, -1) if lines[j]["speaker"] != sp), None)
        listener = prev_sp if prev_sp in others else (others[0] if others else None)
        # reaction cutaway only in the middle of a really long line (the speaker keeps talking off-screen)
        if cam == "close" and listener and d > 6.0:
            mid = l["start"] + d * 0.5
            shots.append({"start": mid, "kind": "close", "focus": listener, "push": 0.04, "shake": None})
            shots.append({"start": mid + 1.2, "kind": "close", "focus": sp, "push": 0.05, "shake": None})
        # reaction shot in the pause after a line: the listener's face tells the joke
        gap = (nxt["start"] if nxt else duration) - l["end"]
        if others and gap > 0.55 and (strong or "?" in text or gap > 1.2 or cam == "close"):
            c = nxt["speaker"] if nxt and nxt["speaker"] != sp else listener
            if not (nxt and nxt["speaker"] == c and gap < 0.9):  # the next line will cut to them anyway
                shots.append({"start": l["end"] + 0.12, "kind": "close", "focus": c, "push": 0.04, "shake": None})
    plan["shots"] = shots
    return _finish(plan, duration, min_len=0.6, later_wins=True)


def _finish(plan, duration, min_len=0.8, later_wins=False):
    shots = sorted(plan["shots"] or [{"start": 0, "kind": "wide", "focus": None, "push": 0.03, "shake": None}],
                   key=lambda s: s["start"])
    shots[0]["start"] = 0.0
    merged = []
    for s in shots:  # no shot shorter than min_len, no two identical shots in a row
        if merged and (s["start"] - merged[-1]["start"] < min_len):
            if later_wins and len(merged) > 1:  # held style
                # a shot of someone SPEAKING is never dropped or moved: the speaker must be on screen
                if s.get("line") and merged[-1].get("line"):
                    if (s["kind"], s["focus"]) != (merged[-1]["kind"], merged[-1]["focus"]):
                        merged.append(s)
                elif s.get("line"):  # a reaction shot is in the way: the speaker's shot replaces it
                    merged[-1] = s
                continue  # a reaction shot too close to a speaking shot is skipped
            if s["kind"] == "close" and merged[-1]["kind"] == "wide" and len(merged) > 1:
                merged[-1] = {**s, "start": merged[-1]["start"]}
            continue
        if merged and s["kind"] == merged[-1]["kind"] and s["focus"] == merged[-1]["focus"]:
            continue
        merged.append(s)
    for a, b in zip(merged, merged[1:] + [None]):
        a["end"] = duration if b is None else b["start"]
    plan["shots"] = merged
    plan["scenes"][-1]["end"] = duration
    plan["duration"] = duration
    return plan


# ------------------------------------------------------------------ optional smart director (Claude API)
PROMPT = """You direct a short, simple 2D cartoon (flat cartoon characters, expressive faces, simple gestures).
For every spoken line pick how the scene should behave so the story reads clearly and is funny/expressive.

CHARACTERS: {cast}
STORY NOTES: {notes}
MENUS (use only these words):
emotion: {emotions}
gesture: {gestures}
body: {body}
emote: {emotes} or "none"
camera: wide (both characters in frame — use when they do something together: hug, give, fight, push) |
        close (only the speaker in frame — the default for normal talking)

LINES (id. speaker [start-end] text):
{lines}

Return ONLY JSON: {{"location": "<one of {locations}>", "lines": [{{"id": 0, "emotion": "...", "intensity": 1,
"gesture": "...", "body": "...", "emote": "...", "camera": "...", "listener_emotion": "..."}}]}}
intensity is 0 (calm), 1 (clear) or 2 (strong). Leave quiet lines plain; use close-ups for punchlines and strong
emotion; the listener should react believably to what is said."""


def smart_overrides(lines, cast, notes, api_key, model, log=print):
    import anthropic
    from . import backgrounds
    client = anthropic.Anthropic(api_key=api_key)
    txt = "\n".join(f'{i}. {l["speaker"]} [{l["start"]:.1f}-{l["end"]:.1f}] {l.get("text") or "(no words)"}'
                    for i, l in enumerate(lines))
    msg = client.messages.create(model=model, max_tokens=8000, messages=[{"role": "user", "content": PROMPT.format(
        cast=", ".join(cast), notes=notes or "(none)", emotions=", ".join(EMOTIONS), gestures=", ".join(GESTURES),
        body=", ".join(BODY), emotes=", ".join(EMOTES), lines=txt,
        locations=", ".join(backgrounds.list_locations()))}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    return {int(x.get("id", -1)): x for x in data.get("lines", [])}, data.get("location")


def make_plan(lines, cast, locations, notes, duration, settings, log=print):
    key = (settings.get("claude_api_key") or "").strip()
    over, loc = None, None
    by = "built-in"
    if key and lines:
        try:
            log("Smart director is reading the dialogue…")
            over, loc = smart_overrides(lines, cast, notes, key, settings.get("claude_model") or "claude-sonnet-5-5",
                                        log)
            by = "smart"
        except Exception as e:
            log(f"Smart director unavailable ({type(e).__name__}); using the built-in director.")
    if (not locations or locations == ["Auto"]) and loc:
        locations = [loc]
    plan = rule_plan(lines, cast, locations, notes, duration, seed=int(duration * 1000) % 9973, overrides=over)
    if settings.get("motion", "held") == "held":
        plan = held_shots(plan, lines, cast, notes, duration, over)
    plan["by"] = by
    plan["motion"] = settings.get("motion", "held")
    return plan
