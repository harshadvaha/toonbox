#!/bin/bash
# Double-click to get the newest Toonbox from GitHub. Your characters, videos and settings are NOT touched
# (they live in Documents/Toonbox Data). Close the Toonbox window first.
cd "$(dirname "$0")"
echo "Current version: $(cat VERSION 2>/dev/null || echo unknown)"
TMP="$(mktemp -d)"
echo "Downloading the latest Toonbox…"
if ! curl -fsSL -o "$TMP/toonbox.zip" https://github.com/harshadvaha/toonbox/archive/refs/heads/main.zip; then
  echo "Couldn't download (check the internet connection). Nothing was changed."; read -n 1 -p "Press any key to close."; exit 1
fi
unzip -q "$TMP/toonbox.zip" -d "$TMP"
rsync -a --exclude ".venv" "$TMP/toonbox-main/" ./
chmod +x start.command "Update Toonbox.command"
rm -rf "$TMP"
echo "Updated to version $(cat VERSION). Open start.command to use it."
read -n 1 -p "Press any key to close."
