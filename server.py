"""Vipy PC server. Run: python server.py
Needs a .env file next to it:  LLM_API_KEY=your_groq_key
Optional: LLM_BASE_URL, LLM_MODEL, HOST
"""
import json, os, subprocess, time, urllib.parse, webbrowser
from pathlib import Path

import pyautogui, pyperclip, uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from openai import OpenAI
from pydantic import BaseModel

ENV = Path(__file__).parent / ".env"
load_dotenv(ENV)
if not os.getenv("LLM_API_KEY"):
    raise SystemExit(f"LLM_API_KEY not found. Looked for: {ENV} (exists: {ENV.exists()}).\n"
                     "The file must be named exactly .env (not .env.txt) and contain one line: LLM_API_KEY=your_key")
client = OpenAI(api_key=os.environ["LLM_API_KEY"],
                base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"))
# Groq retires models every few months, so we try each one in order until one answers.
MODELS = [m for m in (os.getenv("LLM_MODEL"), "openai/gpt-oss-120b", "openai/gpt-oss-20b") if m]

def complete(msgs):
    for m in MODELS:
        try:
            extra = {"reasoning_effort": "low"} if "gpt-oss" in m else {}  # low = faster replies
            return client.chat.completions.create(model=m, messages=msgs, tools=TOOLS, **extra).choices[0].message
        except Exception as e:
            print(f"[error] model {m}: {e}")
    raise RuntimeError("all models failed, see [error] lines above")

SYSTEM = ("You are Vipy, a friendly voice assistant living on a phone next to the user's PC. "
          "Your replies are spoken aloud: use one or two short sentences, no markdown, no emojis. "
          "Answer questions directly. Use tools when asked to do something on the PC "
          "(open apps, open websites, search, type text, volume or media keys). "
          "If you can't do something, say so briefly. Reply in the language the user spoke.")

# ---- PC actions (Windows). Only these can run: Vipy never executes arbitrary commands. ----
APPS = {"notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
        "file explorer": "explorer.exe", "task manager": "taskmgr.exe"}
KEYS = {"volume_up": "volumeup", "volume_down": "volumedown", "mute": "volumemute",
        "play_pause": "playpause", "next_track": "nexttrack", "previous_track": "prevtrack"}

def open_app(name):
    exe = APPS.get(name.lower())
    if not exe:
        return f"Not allowed. I can open: {', '.join(APPS)}"
    subprocess.Popen(exe)
    time.sleep(1.5)  # let the window appear so type_text lands in it
    return "opened"

def open_url(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return "opened"

def web_search(query):
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote_plus(query))
    return "search opened"

def type_text(text):
    pyperclip.copy(text)  # paste instead of typing: handles any language and symbol
    pyautogui.hotkey("ctrl", "v")
    return "typed into the focused window"

def media_key(action):
    if action not in KEYS:
        return f"Unknown action. Use one of: {', '.join(KEYS)}"
    pyautogui.press(KEYS[action])
    return "done"

def T(name, desc, /, **props):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": {k: {"type": "string", "description": v} for k, v in props.items()},
        "required": list(props)}}}

TOOLS = [
    T("open_app", f"Open a desktop app. Allowed: {', '.join(APPS)}", name="App name"),
    T("open_url", "Open a website in the default browser", url="Full URL or domain"),
    T("web_search", "Search Google in the default browser", query="Search text"),
    T("type_text", "Type text into the currently focused window (open the app first)", text="Text to write"),
    T("media_key", f"Press a media key: {', '.join(KEYS)}", action="One of the listed actions"),
]
FUNCS = {f.__name__: f for f in (open_app, open_url, web_search, type_text, media_key)}

# ---- Server ----
app = FastAPI()
history = []  # last few user/assistant turns, so Vipy remembers the conversation

class Msg(BaseModel):
    text: str

BASE = Path(__file__).parent  # only the files below are served, never the whole folder (.env stays private)
MANIFEST = {"name": "Vipy", "short_name": "Vipy", "start_url": "/", "display": "fullscreen",
            "display_override": ["fullscreen", "standalone"], "orientation": "landscape",
            "background_color": "#121a74", "theme_color": "#121a74",
            "icons": [{"src": f"/icon-{s}.png", "sizes": f"{s}x{s}", "type": "image/png", "purpose": "any maskable"}
                      for s in (192, 512)]}

@app.get("/")
def index():
    return FileResponse(BASE / "index.html")

@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse(MANIFEST, media_type="application/manifest+json")

@app.get("/sw.js")
def service_worker():
    return Response("self.addEventListener('fetch',()=>{});", media_type="text/javascript")

@app.get("/icon-{size}.png")
def icon(size: int):
    if size not in (192, 512):
        raise HTTPException(404)
    return FileResponse(BASE / f"icon-{size}.png", media_type="image/png")

@app.post("/chat")
def chat(m: Msg):
    history.append({"role": "user", "content": m.text})
    del history[:-12]
    msgs = [{"role": "system", "content": SYSTEM}] + history
    try:
        for _ in range(4):  # allow a few tool-call rounds
            msg = complete(msgs)
            if not msg.tool_calls:
                break
            msgs.append({"role": "assistant", "content": msg.content or "", "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in msg.tool_calls]})
            for c in msg.tool_calls:
                try:
                    out = FUNCS[c.function.name](**json.loads(c.function.arguments))
                except Exception as e:
                    out = f"error: {e}"
                print(f"[tool] {c.function.name} {c.function.arguments} -> {out}")
                msgs.append({"role": "tool", "tool_call_id": c.id, "content": str(out)})
        reply = msg.content or "Done."
    except Exception as e:
        print("[error]", e)
        reply = "I couldn't reach my brain. Check the API key or the internet."
    history.append({"role": "assistant", "content": reply})
    return {"reply": reply}

if __name__ == "__main__":
    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=8000)
