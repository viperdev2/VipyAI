# Vipy

A tiny voice assistant with a face. Your **phone** is the microphone, speaker and screen. Your **PC** does the work. Say "open notepad", "search for cats" or "volume up" and Vipy does it on your computer.

## How it works

```
Phone (Chrome)  --USB-->  PC (server.py)  -->  LLM API
  mic + voice               FastAPI           decides what to do
  animated face             runs PC actions
```

1. Tap the phone screen and talk. Chrome turns your speech into text.
2. The text is sent to `server.py` running on your PC.
3. The server asks an LLM (Groq by default, any OpenAI-compatible API works). The LLM can answer, or call one of a few allowed PC actions.
4. The reply is spoken out loud on the phone.

**Safe by design:** Vipy can only run a fixed list of actions: open a few apps (Notepad, Calculator, Paint, File Explorer, Task Manager), open a website, search Google, type text, and press media keys. It never runs arbitrary commands.

## Requirements

- Windows PC with Python 3.9+
- Android phone with Chrome and a USB cable
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) (for `adb`)
- An LLM API key, for example a free one from [Groq](https://console.groq.com/keys)

## Setup

```bash
pip install fastapi uvicorn openai python-dotenv pyautogui pyperclip
```

Create a file named `.env` (exactly that, not `.env.txt`) next to `server.py`:

```
LLM_API_KEY=your_key_here
```

## Run

**1. On the PC**, start the server and leave it open:

```bash
python server.py
```

**2. On the phone**, turn on Developer options and **USB debugging**, then plug it into the PC and accept the prompt.

**3. On the PC**, in a second terminal:

```bash
adb devices
adb reverse tcp:8000 tcp:8000
```

**4. On the phone**, open Chrome and go to `http://localhost:8000`. Tap the screen, allow the microphone, and talk.

> Why USB? Chrome only allows the microphone on `localhost` or HTTPS, and `adb reverse` makes the phone's `localhost` point to your PC. Run `adb reverse` again each time you replug the phone.

Tip: use Chrome's menu, **Install app**, for a fullscreen app on your home screen.

## Options

| Setting | Where | Default |
|---|---|---|
| `LLM_API_KEY` | `.env` | required |
| `LLM_BASE_URL` | `.env` | Groq's API |
| `LLM_MODEL` | `.env` | `openai/gpt-oss-120b`, with fallbacks |
| `HOST` | `.env` | `127.0.0.1` |
| Language | URL, e.g. `?lang=fr-FR` | `en-US` |

To allow more apps, add them to the `APPS` dictionary in `server.py`.

## Troubleshooting

- **"LLM_API_KEY not found"**: the file must be called `.env` and sit next to `server.py`.
- **"I couldn't reach my brain"**: the API key is wrong or the model was retired. Check the `[error]` lines in the PC terminal.
- **"Can't reach the PC"**: the server isn't running, or you need to run `adb reverse` again.
- **"Mic blocked"**: allow the microphone for the site in Chrome's settings.

## Security

Never commit your `.env` file. Keep `HOST` at `127.0.0.1`: the server has no password, so exposing it to your network would let anyone on it control your PC.
