# notify.py: fire-and-forget Telegram messages. Reads TELEGRAM_TOKEN and TELEGRAM_CHAT_ID from the environment
# (set via env_file: .env). Never raises: returns silently if either variable is missing or the call fails.
# Lives in strategies/ because only ./strategies and config.json are bind-mounted into the container.
import json
import os
import urllib.request


def tg(text):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps({"chat_id": chat_id, "text": text}).encode(),
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10).close()
    except Exception:
        return
