# Toonbox — notes for future updates

Owner: Harshad (not a coder). Explain changes in plain language. In anything user-facing, never mention
Claude/AI/Anthropic as the creator ("Made by Harshad").

## Layout
- `toonbox/` app code (Python). Entry: `toonbox/app.py` (Gradio UI, 4 tabs).
  - `toon.py` character drawing (skia vectors, expressions, visemes) · `props.py` prop library + keywords
  - `director.py` audio/words → storyboard (emotions, gestures, reactions, camera, props)
  - `anim.py` per-frame poses with springs · `render.py` stage/camera → MP4 via ffmpeg
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
- Test before pushing: `python -c "from toonbox import app; app.build()"` and render a short video
  (see `pipeline.make_video(..., end=5)`).
