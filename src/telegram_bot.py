# FILE PATH: src/telegram_bot.py (v8.2 - Fixed pair/RR/ADX)
import requests
import config
import os
import logging

session = requests.Session()


def get_proxy():
    return getattr(config, 'PROXY', None)


def send_telegram_message(text):
    token   = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")   or getattr(config, 'TELEGRAM_CHAT_ID',   None)

    if not token or not chat_id:
        logging.warning("توکن یا Chat ID تلگرام تنظیم نشده است.")
        return

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    try:
        proxy    = get_proxy()
        response = session.post(url, json=payload, timeout=15,
                                proxies={"https": proxy} if proxy else None)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"خطای شبکه در ارسال به تلگرام: {e}")


def format_and_send_signal(signal_data):
    """ارسال سیگنال هوشمند سیستم v8.2"""
    d = signal_data

    icon       = "🟢 #LONG" if d.get('direction') == "LONG" else "🔴 #SHORT"

    # FIX 1: هر دو کلید pair و pair_display رو چک می‌کنیم
    raw_pair   = d.get('pair') or d.get('pair_display') or 'UNKNOWN'
    clean_pair = str(raw_pair).replace('_', '/')

    # FIX 2: R:R همیشه مثبت — برای LONG و SHORT هر دو درست
    try:
        sl_dist  = abs(float(d['entry_price']) - float(d['stop_loss']))
        tp_dist  = abs(float(d['tp2'])         - float(d['entry_price']))
        rr_ratio = round(tp_dist / sl_dist, 1) if sl_dist > 0 else 0
    except Exception:
        rr_ratio = 0

    # FIX 3: ADX از feat_adx یا adx_score
    adx_val = d.get('feat_adx') or d.get('adx_score') or 0

    message = (
        f"<b>{icon} سیگنال سیستم v8.0</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 <b>جفت ارز:</b> <code>{clean_pair}</code>\n"
        f"💵 <b>ورود:</b> <code>{d.get('entry_price')}</code>\n"
        f"🛑 <b>استاپ:</b> <code>{d.get('stop_loss')}</code>\n"
        f"🎯 <b>تارگت ۱:</b> <code>{d.get('tp1')}</code>\n"
        f"🎯 <b>تارگت ۲:</b> <code>{d.get('tp2')}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚖️ <b>حجم پوزیشن:</b> <code>{d.get('position_size', 0)} USDT</code>\n"
        f"📊 <b>نسبت R:R:</b> <code>{rr_ratio}</code>\n"
        f"📈 <b>قدرت روند (ADX):</b> <code>{round(float(adx_val), 1)}</code>\n"
        f"🧠 <i>وضعیت: تایید شده توسط مدل اختصاصی {clean_pair}</i>"
    )
    send_telegram_message(message)


def send_heartbeat_report(watchlist_count, model_count):
    message = (
        f"🤖 <b>Status: System Online</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌐 <b>واچ‌لیست فعال:</b> <code>{watchlist_count} ارز</code>\n"
        f"🧠 <b>مدل‌های هوش مصنوعی فعال:</b> <code>{model_count}</code>\n"
        f"⏳ <b>وضعیت شبکه:</b> <code>Stable (OK)</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>ربات در حال رصد دقیق بازار است...</i>"
    )
    send_telegram_message(message)
