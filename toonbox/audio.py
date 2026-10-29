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
    """Speech-to-text with word timings. Falls back to plain speech detection if the model is missing."""
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        log(f"Speech-to-text not available ({e}); detecting speech by loudness only.")
        return energy_segments(load_wav(path)), False
    try:
        log(f"Loading speech-to-text model ({model_name}) — first time downloads it, please wait…")
        model = WhisperModel(model_name, device="cpu", compute_type="int8", download_root=str(MODELS))
        segs, info = model.transcribe(str(path), language=language or None, word_timestamps=True,
                                      vad_filter=True, beam_size=5)
        out = []
        for s in segs:
            words = list(s.words or [])
            if not words:
                out.append({"start": s.start, "end": s.end, "text": s.text.strip()})
                continue
            # split a segment where there is a clear pause — often a change of speaker
            cur = [words[0]]
            for w in words[1:]:
                if w.start - cur[-1].end > 0.45:
                    out.append(_join(cur))
                    cur = [w]
                else:
                    cur.append(w)
            out.append(_join(cur))
        log(f"Heard {len(out)} lines (language: {info.language}).")
        return [o for o in out if o["end"] - o["start"] > 0.1], True
    except Exception as e:
        log(f"Speech-to-text failed ({e}); detecting speech by loudness only.")
        return energy_segments(load_wav(path)), False


def _join(words):
    return {"start": round(words[0].start, 2), "end": round(words[-1].end, 2),
            "text": "".join(w.word for w in words).strip()}


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


_ecapa = None


def _ecapa_embed(chunks, log):
    global _ecapa
    import torch
    from speechbrain.inference.speaker import EncoderClassifier
    if _ecapa is None:
        log("Loading voice-recognition model — first time downloads it…")
        _ecapa = EncoderClassifier.from_hparams(source="speechbrain/spkrec-ecapa-voxceleb",
                                                savedir=str(MODELS / "ecapa"), run_opts={"device": "cpu"})
    embs = []
    for c in chunks:
        with torch.no_grad():
            e = _ecapa.encode_batch(torch.tensor(c).unsqueeze(0)).squeeze().numpy()
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


def assign_speakers(path, lines, k, log=print):
    """Group lines into k voices. Speaker numbers follow the order voices are first heard."""
    if k <= 1 or len(lines) == 0:
        for l in lines:
            l["speaker"] = 0
        return lines
    y = load_wav(path)
    chunks = []
    for l in lines:
        a, b = int(l["start"] * SR), int(l["end"] * SR)
        c = y[a:b]
        if len(c) < SR * 0.4:  # pad very short lines with context
            mid = (a + b) // 2
            c = y[max(0, mid - int(SR * 0.3)): mid + int(SR * 0.3)]
        chunks.append(c)
    X = None
    try:
        X = _ecapa_embed(chunks, log)
        method = "voice-recognition model"
    except Exception as e:
        log(f"Advanced voice model not available ({type(e).__name__}); using built-in voice matching.")
    if X is None:
        X = np.array([_mfcc_pitch(c) for c in chunks])
        X = (X - X.mean(0)) / (X.std(0) + 1e-6)
        X[:, -1] *= 4.0  # pitch is the strongest clue for telling e.g. child / mother / father apart
        X[:, :-1] *= 0.5
        method = "built-in voice matching"
    # cluster the clearer lines first, then attach very short ones to the nearest voice
    durs = np.array([l["end"] - l["start"] for l in lines])
    longi = np.where(durs >= 0.3)[0]
    if len(longi) < k:
        longi = np.argsort(-durs)[: max(k, len(lines))]
    lab_long = _cluster(X[longi], k)
    cents = np.array([X[longi][lab_long == c].mean(0) for c in range(k) if (lab_long == c).any()])
    labs = np.array([np.argmin(((cents - x) ** 2).sum(1)) for x in X])
    labs[longi] = lab_long[: len(longi)] if len(cents) == k else labs[longi]
    order = []
    for lb in labs:
        if lb not in order:
            order.append(lb)
    remap = {lb: i for i, lb in enumerate(order)}
    for l, lb in zip(lines, labs):
        l["speaker"] = int(remap[lb])
    found = len(order)
    log(f"Found {found} voice(s) using {method}.")
    return lines


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
