import json
import os
import sys
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/models?output_modalities=all"
STATE_FILE = "models.json"


def send_notification(text):
    tg_token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    ntfy_topic = os.environ.get("NTFY_TOPIC", "").strip()

    if tg_token and tg_chat:
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        payload = json.dumps({
            "chat_id": tg_chat,
            "text": text,
            "disable_web_page_preview": True
        }).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print(f"Telegram hatasi: {e}")

    if ntfy_topic:
        url = f"https://ntfy.sh/{ntfy_topic}"
        req = urllib.request.Request(
            url,
            data=text.encode("utf-8"),
            headers={"Title": "OpenRouter Stealth Radar", "Priority": "high"}
        )
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print(f"ntfy hatasi: {e}")


def is_stealth_model(m):
    m_id = m.get("id", "").lower()
    name = (m.get("name") or "").lower()
    desc = (m.get("description") or "").lower()

    # 1. Resmi stealth/ saglayicisi (ox-alpha, crouton-alpha, space-bunny-alpha vb.)
    if m_id.startswith("stealth/"):
        return True

    # 2. ID veya isimde dogrudan "stealth" geciyorsa
    if "stealth" in m_id or "stealth" in name:
        return True

    # 3. Aciklamada aktif stealth/gizli model oldugu yaziyorsa
    if "is a stealth model" in desc or "is an anonymous" in desc:
        return True

    return False


def main():
    req = urllib.request.Request(
        OPENROUTER_URL,
        headers={"User-Agent": "OpenRouter-Stealth-Radar/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"API hatasi, bu tur atlaniyor: {e}")
        sys.exit(0)

    models = data.get("data", [])
    if not models:
        print("Bos model listesi, atlaniyor.")
        sys.exit(0)

    is_first_run = not os.path.exists(STATE_FILE)
    if not is_first_run:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            # Eski sozluk formatindan liste formatina sorunsuz gecis
            known_ids = set(loaded.keys() if isinstance(loaded, dict) else loaded)
    else:
        known_ids = set()

    # Sadece stealth modelleri filtrele
    current_stealth = [m for m in models if is_stealth_model(m)]
    current_ids = sorted([m["id"] for m in current_stealth])

    if set(current_ids) != known_ids:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(current_ids, f, indent=2)

    if is_first_run:
        send_notification(
            f"✅ OpenRouter Stealth Radar Başlatıldı!\n"
            f"Şu an aktif stealth model sayısı: {len(current_ids)}"
        )
        return

    # Yeni eklenen stealth modelleri bildir
    for m in current_stealth:
        if m["id"] not in known_ids:
            ctx_len = m.get("context_length")
            ctx = f"{round(ctx_len / 1024)}K" if ctx_len else "?"
            msg = (
                f"🕵️‍♂️ YENİ STEALTH MODEL!\n"
                f"🤖 İsim: {m.get('name', m['id'])}\n"
                f"🆔 ID: {m['id']}\n"
                f"📏 Context: {ctx}\n"
                f"🔗 https://openrouter.ai/{m['id']}"
            )
            send_notification(msg)


if __name__ == "__main__":
    main()
