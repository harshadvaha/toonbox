# Toonbox — notes for future updates

Owner: Harshad (not a coder). Explain changes in plain language. In anything user-facing, never mention
Claude/AI/Anthropic as the creator ("Made by Harshad").

## Layout
- `toonbox/` app code (Python). Entry: `toonbox/app.py` (Gradio UI, 4 tabs).
  - `toon.py` character drawing (skia vectors, expressions, visemes) · `props.py` prop library + keywords
  - `director.py` audio/words → storyboard (emotions, gestures, reactions, camera, props)
  - `anim.py` per-frame poses with springs ("smooth" style) · `held.py` held-pose style (default): snaps, mouth on 2s, 2-4 drawing loops · `render.py` stage/camera → MP4 via ffmpeg
  - `audio.py` speech-to-text (faster-whisper), speakers, loudness · `lipsync.py` Rhubarb/built-in
  - `pipeline.py` glue · `jobs.py` background jobs, stop, draft restore · `cast.py` saved characters + voice memory
  - `paths.py` all locations · `setup_tools.py` first-run downloads
- `starter/characters/` sample cast copied into the user's data on first run.
- User data is OUTSIDE the app: `~/Documents/Toonbox Data/` (library, videos, settings, models, tools, work).
  Never move user data back into the app folder; never delete it.

## Rules
- Keep everything free/local; paid/online features must be optional.
- Never overwrite user files; saving a character again creates a new version; videos get new names.
- Bump `VERSION` and `pyproject.toml` version for each release; push to `main` — the user runs
  "Update Toonbox.command" (downloads main.zip, keeps .venv and user data).
- Motion style lives in settings `motion` ("held" default / "smooth"). Held mode also changes the camera: `director.held_shots`
  (cut to speaker, reaction cutaways, wide two-shot on TOGETHER words), and close-ups hide the other characters.
- Test before pushing: `python -c "from toonbox import app; app.build()"` and render a short video
  (see `pipeline.make_video(..., end=5)`).

## 3.4.0 notes
- faster-whisper gets a numpy array (audio.load_wav), never a file path: av 19 breaks its file decoding.
- Speakers: free CAM++ voice model via sherpa-onnx (models/voice-campplus.onnx, downloaded from GitHub).
  Lines are short (split at pauses + question→answer word cues), so the 'Who' column is easy to correct.
  Same-performer voices can't be separated reliably — the review table is the real fix.
- Camera: a speaking shot is never moved/dropped by `_finish`; reactions go to the person being answered.
- Indian-script subtitles are drawn with Pillow (raqm) using toonbox/fonts/NotoSansDevanagari-Bold.ttf.
- app.py allowed_paths includes DATA (videos live outside the app folder).
