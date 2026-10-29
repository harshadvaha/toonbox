# Toonbox — simple-style cartoon videos from your audio

Made by Harshad.

You give it an audio file and pick characters from your saved cast. Toonbox works out who speaks when, then directs the scene: faces, gestures, reactions, props and camera shots. It saves the finished MP4. Everything runs on your Mac, and nothing is paid per video.

## Start

**First time:** on https://github.com/harshadvaha/toonbox press **Code → Download ZIP**, unzip it (for example, into Documents) and follow the steps below.

**Updating later:** double-click **Update Toonbox.command**. It fetches the newest version from GitHub. Your characters, videos and settings are never touched, because they live separately in `Documents/Toonbox Data`. Deleting or replacing the app folder doesn't lose them either.


1. Unzip the folder anywhere (for example, in Documents).
2. Double-click **start.command**.
   - The first time, macOS may say it's from an unidentified developer. Right-click the file, choose **Open**, then click **Open** again.
   - The first start sets things up and takes 5–10 minutes. After that, it opens in a few seconds.
3. Toonbox opens in your browser. Keep the black window open while you use it.

## Make a video

1. **Characters tab**: create each character once. Pick a body style (Blob, Stick or Simple clothes), head, colours, hair, eyes and extras, then press **Save**. Your cast is ready: Meera, Raju and Golu are included to start with.
2. **New video tab**:
   - Add the audio.
   - Pick **Who speaks**. The first time, pick them in the order they first speak.
   - Leave **Location** on **Auto**, or pick one.
   - Optionally add a line of scene notes, for example "A couple having a conversation in their bedroom".
3. Press **1 · Listen to audio**. A table shows each line and who says it. Fix the **Who** column if something is wrong.
   Pick the **Aspect ratio**: 9:16 (Shorts / Reels) or 16:9 (YouTube).
4. Press **Preview first 15 s** to check quickly, or **2 · Make video** for the whole thing. Videos are saved in `Documents/Toonbox Data/videos` and are never overwritten.

## What it does by itself

- **Who speaks:** voices are grouped automatically. After each finished video, the app remembers each character's voice, so in the next episode it matches voices to characters on its own.
- **Lip-sync and blinks:** on every frame.
- **Expressions:** neutral, happy, laugh, angry, shocked, sad, tired, unimpressed, smug, suspicious, confused, scared, love, awkward, thinking. They're chosen from the words, punctuation, loudness and pitch of each line.
- **Gestures:** pointing, shrugging, hands up, crossed arms, hands on hips, waving, beckoning, facepalm, chin-scratch, hand on chest, a phone to the ear, and hand beats that follow the voice.
- **Reactions:** the listener reacts to what's said, for example flinching when shouted at, or looking awkward when accused.
- **Camera:** an opening wide shot, close-ups on strong lines, reaction shots in pauses, slow push-ins, and a shake on shouted lines.
- **Props from the dialogue:** "laptop" or "office" brings a desk with laptops, "call" puts a phone in a hand, "dog" makes a dog walk in, "pack my stuff" brings a suitcase, and "my necklace" puts the necklace on the character who says it. There are 33 built-in props, listed in the **Props & places** tab.
- **Locations:** Living room, Kitchen, Bedroom, Office, Classroom, Park, Street and Plain studio. With **Auto**, one is picked from the words and your notes.

## Make it yours

- **Your own props:** in the **Props & places** tab, upload a PNG, say where it goes (floor, back, hand or front) and which words bring it in.
- **Your own backgrounds:** upload any image as a new location.
- **Back up your cast:** in the **Characters** tab, use **Export**. Import the file on another Mac.
- **Smart director (optional):** in **Settings**, add a Claude API key. The director then understands the meaning of the dialogue, not just keywords. It costs a few paise per video.

## Good to know

- Nothing you enter is lost if the page reloads or the screen turns off. Your audio, picks, notes and the table come back, and a video that's being made keeps going, with progress showing again. While Toonbox is open, the Mac is kept awake. Closing the lid still sleeps it.
- The speech-to-text model (about 1.6 GB) downloads once, during the first start, in the black window.

- Rhubarb lip-sync is installed on the first start. On Apple Silicon Macs it asks to install Apple's Rosetta once. If that's skipped, a built-in lip-sync is used.
- A 1-minute vertical video takes roughly 2–4 minutes to make.
- **While a video is being made:** the panel shows what's happening, the percentage and the time left. A live view shows the frames as they're drawn. The other buttons are locked so you can't start a second job by mistake. **⏹ Stop** asks you to confirm first, and stopping keeps your inputs.
- Earlier versions (v1, v2) are separate folders and still work.
