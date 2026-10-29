#!/bin/bash
# Double-click this file to open Toonbox. First run sets everything up (5–10 minutes, needs internet).
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv (small tool that manages Python for Toonbox)…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
echo "Getting Toonbox ready… (first time is slow, later starts take a few seconds)"
uv run --python 3.12 python -m toonbox.setup_tools
echo "Opening Toonbox in your browser. Keep this window open while you use it."
# caffeinate keeps the Mac awake while Toonbox is open (the screen may still dim)
caffeinate -i uv run --python 3.12 python -m toonbox.app
