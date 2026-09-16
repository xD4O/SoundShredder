"""Run `python app.py` to open SoundShredder on this computer."""

import argparse
import threading
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from soundshredder.certificates import configure_macos_certificates


def main():
    configure_macos_certificates()
    parser = argparse.ArgumentParser(description="SoundShredder — local dialogue, music and effects separation")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    try:
        with urllib.request.urlopen(url + "/api/system", timeout=2) as response:
            import json

            if json.load(response).get("name") == "SoundShredder":
                print(f"SoundShredder is already running at {url}")
                if not args.no_browser:
                    webbrowser.open(url)
                return
    except (OSError, ValueError):
        pass
    if not args.no_browser:
        threading.Timer(2, lambda: webbrowser.open(url)).start()
    print(f"\nSoundShredder: {url}\nKeep this window open. Press Ctrl+C to stop.\n")
    uvicorn.run("soundshredder.server:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
