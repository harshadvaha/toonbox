"""Listen to the audio: find spoken lines, who says each one, and how loud it is."""
import subprocess

import numpy as np
from scipy.cluster.vq import kmeans2
from scipy.fft import dct, rfft
from scipy.signal import get_window

from .paths import MODELS, ffmpeg_exe

SR = 16000


def load_wav(path, sr=SR):
    cmd = [ffmpeg_exe(), "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def to_wav(path, out, sr=22050):
    cmd = [ffmpeg_exe(), "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", str(sr), str(out)]
    subprocess.run(cmd, check=True)
    return out


# ------------------------------------------------------------------ speech regions
def energy_segments(y, sr=SR, min_gap=0.35, min_len=0.25):
    hop = int(sr * 0.02)
    n = len(y) // hop
    e = np.sqrt(np.mean(y[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(e)
    floor = np.percentile(db, 10)
    peak = np.percentile(db, 95)
    thr = floor + 0.35 * (peak - floor)
    on = db > thr
    segs = []
    i = 0
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            segs.append([i * hop / sr, j * hop / sr])
            i = j
        else:
            i += 1
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return [{"start": round(a, 2), "end": round(b, 2), "text": ""} for a, b in merged if b - a >= min_len]


def transcribe(path, language=None, model_name="large-v3-turbo", log=print):
    """Speech-to-text with word timings. Falls back to plain speech detection if the model is missing.
    Each line keeps its words (start, end, text) so speakers can be decided word by word later."""
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        log(f"Speech-to-text not available ({e}); detecting speech by loudness only.")
        return energy_segments(load_wav(path)), False
    try:
        log(f"Loading speech-to-text model ({model_name}) — first time downloads it, please wait…")
        model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=str(MODELS))
        # give the model ready-made audio (decoded by ffmpeg) — avoids a crash in newer audio libraries
        segs, info = model.transcribe(load_wav(path), language=language or None, word_timestamps=True,
                                      vad_filter=True, beam_size=5)
        words = []
        for s in segs:
            for w in (s.words or []):
                if w.word.strip():
                    words.append({"start": round(w.start, 2), "end": round(w.end, 2), "text": w.word.strip()})
        if not words:
            raise RuntimeError("no words heard")
        out = split_lines(words)
        log(f"Heard {len(words)} words in {len(out)} lines (language: {info.language}).")
        return out, True
    except Exception as e:
        log(f"Speech-to-text failed ({e}); detecting speech by loudness only.")
        return energy_segments(load_wav(path)), False


# words that usually START a reply, and words that usually END a question (Hindi / Hinglish / English)
REPLY_START = {"हाँ", "हां", "हा", "नहीं", "नही", "ना", "अरे", "अच्छा", "ओह", "जी", "हम्म", "चल", "चलो", "बस",
               "haan", "han", "ha", "nahi", "nahin", "na", "arre", "are", "achha", "acha", "ji", "yes", "no",
               "yeah", "okay", "ok", "oh", "well"}
QUESTION_END = {"क्या", "ना", "न", "क्यों", "कहाँ", "कैसे", "कौन", "kya", "na", "kyun", "kahan", "kaise"}


def _cue(prev, nxt):
    """How likely a new speaker starts at `nxt` (0..1), from the words alone."""
    p = prev["text"].strip("?!.,।").lower()
    n = nxt["text"].strip("?!.,।").lower()
    sc = 0.0
    if prev["text"].rstrip().endswith(("?", "!", ".", "।")):
        sc += 0.5
    if p in QUESTION_END:
        sc += 0.4
    if n in REPLY_START:
        sc += 0.4
    return min(sc, 1.0)


def split_lines(words, gap=0.3, max_len=3.0):
    """Short lines: break at every pause, at question→answer points, and break long stretches at their best
    break point. Short lines matter — in quick back-and-forth one line must never hold two people."""
    lines, cur = [], [words[0]]
    for w in words[1:]:
        if w["start"] - cur[-1]["end"] > gap or _cue(cur[-1], w) >= 0.8:
            lines.append(cur)
            cur = [w]
        else:
            cur.append(w)
    lines.append(cur)
    out = []
    stack = lines[::-1]
    while stack:
        ws = stack.pop()
        if ws[-1]["end"] - ws[0]["start"] > max_len and len(ws) > 3:
            def score(i):  # pause + word cues, and prefer breaks that leave neither side tiny
                g = ws[i]["start"] - ws[i - 1]["end"]
                bal = min(i, len(ws) - i) / len(ws)
                return g * 3 + _cue(ws[i - 1], ws[i]) + bal * 0.6
            i = max(range(2, len(ws) - 1), key=score)
            stack += [ws[i:], ws[:i]]
        else:
            out.append(_join(ws))
    return out


def _join(words):
    return {"start": round(words[0]["start"], 2), "end": round(words[-1]["end"], 2),
            "text": " ".join(w["text"] for w in words).strip(), "words": words}


# ------------------------------------------------------------------ voice fingerprints
def _mfcc_pitch(y, sr=SR):
    n_fft, hop = 512, 160
    if len(y) < n_fft:
        y = np.pad(y, (0, n_fft - len(y)))
    frames = np.lib.stride_tricks.sliding_window_view(y, n_fft)[::hop] * get_window("hann", n_fft)
    spec = np.abs(rfft(frames, axis=1)) ** 2
    # mel filterbank
    n_mels = 40
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    imel = lambda m: 700 * (10 ** (m / 2595) - 1)
    pts = imel(np.linspace(mel(60), mel(7600), n_mels + 2))
    bins = np.floor((n_fft + 1) * pts / sr).astype(int)
    fb = np.zeros((n_mels, spec.shape[1]))
    for m in range(1, n_mels + 1):
        l, c, r = bins[m - 1], bins[m], bins[m + 1]
        fb[m - 1, l:c] = (np.arange(l, c) - l) / max(1, c - l)
        fb[m - 1, c:r] = (r - np.arange(c, r)) / max(1, r - c)
    melspec = np.log(spec @ fb.T + 1e-9)
    energy = melspec.mean(1)
    keep = energy > np.percentile(energy, 40)
    mf = dct(melspec[keep], type=2, axis=1, norm="ortho")[:, 1:20]
    p = _pitch(y, sr)
    return np.concatenate([mf.mean(0), mf.std(0), [p * 6.0]])


def _pitch(y, sr=SR):
    """Median voice pitch (log Hz) using the YIN method on voiced frames."""
    N, hop = 1024, 320
    lo, hi = sr // 500, sr // 65
    if len(y) < N + hi:
        return 5.2
    frames = np.lib.stride_tricks.sliding_window_view(y, N + hi)[::hop]
    rms = np.sqrt((frames ** 2).mean(1))
    frames = frames[rms > np.percentile(rms, 50)]
    out = []
    for f in frames[:200]:
        x = f[:N]
        d = np.array([np.sum((x - f[tau:tau + N]) ** 2) for tau in range(hi)])
        cm = d[1:] * np.arange(1, hi) / (np.cumsum(d[1:]) + 1e-12)
        cm = np.concatenate([[1.0], cm])
        cand = np.where(cm[lo:] < 0.15)[0]
        if len(cand) == 0:
            continue
        tau = lo + cand[0]
        while tau + 1 < hi and cm[tau + 1] < cm[tau]:
            tau += 1
        out.append(sr / tau)
    return float(np.log(np.median(out))) if out else 5.2


VOICE_MODEL_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
                   "3dspeaker_speech_campplus_sv_zh_en_16k-common_advanced.onnx")
VOICE_MODEL = MODELS / "voice-campplus.onnx"
_voice = None


def get_voice_model(log=print):
    """Free voice-recognition model (CAM++, ~28 MB, runs offline after one download)."""
    global _voice
    if _voice is not None:
        return _voice
    import sherpa_onnx
    if not VOICE_MODEL.exists():
        import urllib.request
        log("Downloading the voice-recognition model (one time, ~28 MB)…")
        tmp = VOICE_MODEL.with_suffix(".part")
        urllib.request.urlretrieve(VOICE_MODEL_URL, tmp)
        tmp.rename(VOICE_MODEL)
    _voice = sherpa_onnx.SpeakerEmbeddingExtractor(
        sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(VOICE_MODEL), num_threads=4))
    return _voice


def _voice_embed(chunks, log):
    ex = get_voice_model(log)
    embs = []
    for c in chunks:
        st = ex.create_stream()
        st.accept_waveform(SR, np.ascontiguousarray(c, dtype=np.float32))
        st.input_finished()
        e = np.array(ex.compute(st))
        embs.append(e / (np.linalg.norm(e) + 1e-9))
    return np.array(embs)


def _cluster(X, k, seed=0):
    from sklearn.cluster import AgglomerativeClustering
    if len(X) <= k:
        return np.arange(len(X))
    try:
        return AgglomerativeClustering(n_clusters=k, linkage="average", metric="cosine").fit_predict(X)
    except Exception:
        _, lab = kmeans2(X, k, seed=seed, minit="++")
        return lab


def _pieces(line, size=1.2):
    """Cut a line into ~1 s pieces at word boundaries, so a speaker change inside a line can be found."""
    ws = line.get("words") or []
    if line["end"] - line["start"] < 3.0 or len(ws) < 4:
        return [ws or [{"start": line["start"], "end": line["end"], "text": line.get("text", "")}]]
    out, cur = [], []
    for w in ws:
        cur.append(w)
        if cur[-1]["end"] - cur[0]["start"] >= size:
            out.append(cur)
            cur = []
    if cur:
        if out and cur[-1]["end"] - cur[0]["start"] < size * 0.5:
            out[-1] += cur
        else:
            out.append(cur)
    return out


def assign_speakers(path, lines, k, log=print):
    """Decide who speaks, piece by piece (~1 s), then re-cut lines wherever the voice changes.
    Speaker numbers follow the order voices are first heard."""
    if k <= 1 or len(lines) == 0:
        for l in lines:
            l["speaker"] = 0
        return lines
    y = load_wav(path)
    pieces = []  # (line index, words)
    for i, l in enumerate(lines):
        for ws in _pieces(l):
            pieces.append((i, ws))
    chunks = []
    for _, ws in pieces:
        a, b = int(ws[0]["start"] * SR), int(ws[-1]["end"] * SR)
        if b - a < SR * 0.8:  # pad very short pieces with a little context
            m = (a + b) // 2
            a, b = max(0, m - int(SR * 0.4)), m + int(SR * 0.4)
        chunks.append(y[a:b])
    X = None
    try:
        X = _voice_embed(chunks, log)
        method = "voice-recognition model"
    except Exception as e:
        log(f"Voice-recognition model not available ({type(e).__name__}: {e}); using built-in voice matching.")
    if X is None:
        X = np.array([_mfcc_pitch(c) for c in chunks])
        X = (X - X.mean(0)) / (X.std(0) + 1e-6)
        X[:, -1] *= 4.0  # pitch is the strongest clue for telling e.g. child / mother / father apart
        X[:, :-1] *= 0.5
        method = "built-in voice matching"
    durs = np.array([ws[-1]["end"] - ws[0]["start"] for _, ws in pieces])
    longi = np.where(durs >= 0.35)[0]
    if len(longi) < k:
        longi = np.argsort(-durs)[:k]
    lab_long = _cluster(X[longi], k)
    cents = np.array([X[longi][lab_long == c].mean(0) for c in range(k) if (lab_long == c).any()])
    labs = np.array([int(np.argmin(((cents - x) ** 2).sum(1))) for x in X])
    if len(cents) == k:
        labs[longi] = lab_long
    # rebuild lines: inside one line, a new speaker starts only where the voice clearly changes
    out = []
    for i, l in enumerate(lines):
        ps = [(lb, ws) for (li, ws), lb in zip(pieces, labs) if li == i]
        groups = []
        for lb, ws in ps:
            if groups and groups[-1][0] == lb:
                groups[-1][1].extend(ws)
            else:
                groups.append([lb, list(ws)])
        # a tiny group (< 0.6 s) is more likely a mistake than a new speaker: give it to its neighbour
        changed = True
        while changed and len(groups) > 1:
            changed = False
            for gi, (lb, ws) in enumerate(groups):
                if ws[-1]["end"] - ws[0]["start"] < 0.6:
                    j = gi - 1 if gi > 0 else gi + 1
                    if j < gi:
                        groups[j][1].extend(ws)
                    else:
                        groups[j][1][:0] = ws
                    groups.pop(gi)
                    changed = True
                    break
        merged = []
        for lb, ws in groups:
            if merged and merged[-1][0] == lb:
                merged[-1][1].extend(ws)
            else:
                merged.append([lb, ws])
        if len(merged) == 1 or not l.get("words"):
            out.append({**l, "speaker": merged[0][0]})
        else:
            for lb, ws in merged:
                out.append({**_join(ws), "speaker": lb})
    order = []
    for l in out:
        if l["speaker"] not in order:
            order.append(l["speaker"])
    remap = {lb: n for n, lb in enumerate(order)}
    for l in out:
        l["speaker"] = int(remap[l["speaker"]])
    log(f"Found {len(order)} voice(s) in {len(out)} lines using {method}. Check the 'Who' column before making the video.")
    return out


def loudness(path, lines):
    y = load_wav(path)
    vals = []
    for l in lines:
        c = y[int(l["start"] * SR): int(l["end"] * SR)]
        vals.append(float(np.sqrt(np.mean(c ** 2) + 1e-12)) if len(c) else 0.0)
    v = np.log(np.array(vals) + 1e-6)
    z = (v - v.mean()) / (v.std() + 1e-6) if len(v) > 1 else np.zeros_like(v)
    for l, zz in zip(lines, z):
        l["loud"] = round(float(zz), 2)
    return lines


def envelope(path, fps):
    """Loudness per video frame, 0..1 (used for the built-in lip-sync)."""
    y = load_wav(path)
    hop = SR / fps
    n = int(len(y) / hop) + 1
    env = np.zeros(n)
    for i in range(n):
        c = y[int(i * hop): int((i + 1) * hop)]
        env[i] = np.sqrt(np.mean(c ** 2)) if len(c) else 0
    return env, len(y) / SR
