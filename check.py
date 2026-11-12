import json
import os
import sys
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/v1/models?output_modalities=all"
STATE_FILE = "models.json"


def to_float(val, default=1.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


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
            headers={"Title": "OpenRouter Radar", "Priority": "high"}
        )
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print(f"ntfy hatasi: {e}")


def main():
    req = urllib.request.Request(
        OPENROUTER_URL,
        headers={"User-Agent": "OpenRouter-Radar/1.0"}
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
            known = json.load(f)
    else:
        known = {}

    new_known = {}
    alerts = []

    for m in models:
        m_id = m["id"]
        pricing = m.get("pricing") or {}
        is_free = (
            to_float(pricing.get("prompt")) == 0.0
            and to_float(pricing.get("completion")) == 0.0
        )
        new_known[m_id] = 1 if is_free else 0

        if is_first_run:
            continue

        was_known = m_id in known
        became_free = was_known and known[m_id] == 0 and is_free

        if not was_known or became_free:
            lower_id = m_id.lower()
            lower_name = (m.get("name") or "").lower()
            is_stealth = ("stealth" in lower_id) or ("stealth" in lower_name)

            # Sadece 0$ olanlar veya ID/isminde "stealth" geçenler
            if is_free or is_stealth:
                alerts.append({
                    "model": m,
                    "is_free": is_free,
                    "reason": "🆕 YENİ MODEL" if not was_known else "💸 ÜCRETSİZ OLDU"
                })

    if new_known != known:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(new_known, f, indent=2, sort_keys=True)

    if is_first_run:
        send_notification(
            f"✅ OpenRouter Radar (GitHub Actions) Başlatıldı!\n"
            f"Hafızaya alınan model sayısı: {len(models)}\n"
            f"Bundan sonra yeni 0$ veya stealth modeller geldiğinde bildirim alacaksınız."
        )
        return

    for item in alerts:
        m = item["model"]
        ctx_len = m.get("context_length")
        ctx = f"{round(ctx_len / 1024)}K" if ctx_len else "?"
        prompt_cost = to_float((m.get("pricing") or {}).get("prompt"), 0.0) * 1e6
        price_text = "ÜCRETSİZ ($0)" if item["is_free"] else f"Prompt: ${prompt_cost:.2f}/M"

        msg = (
            f"{item['reason']}\n"
            f"🤖 İsim: {m.get('name', m['id'])}\n"
            f"🆔 ID: {m['id']}\n"
            f"💰 Fiyat: {price_text}\n"
            f"📏 Context: {ctx}\n"
            f"🔗 https://openrouter.ai/{m['id']}"
        )
        send_notification(msg)


if __name__ == "__main__":
    main()
