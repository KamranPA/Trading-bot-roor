# FILE PATH: src/telegram_bot.py (v8.3 - retry + ADX-zero fix)
# تغییرات نسبت به v8.2:
#   ✅ FIX: send_telegram_message حالا تا ۳ بار با backoff تلاش می‌کند.
#      قبلاً یک قطعی موقت شبکه یعنی سیگنال برای همیشه از دست می‌رفت،
#      چون این ربات فقط سیگنال می‌دهد (بدون معامله‌ی خودکار) و تلگرام
#      تنها مسیر رسیدن سیگنال به کاربر است.
#   ✅ FIX: adx_val دیگر با `or 0` جایگزین نمی‌شود — چون ADX=0 یک مقدار
#      معتبر آماری است و `0 or X` در پایتون همیشه X را برمی‌گرداند
#      (باعث می‌شد adx_score به‌جای ADX خام نمایش داده شود).
import time
import requests
import config
import os
import logging

session = requests.Session()


def get_proxy():
    return getattr(config, 'PROXY', None)


def send_telegram_message(text, max_retries: int = 3):
    token   = os.environ.get("TELEGRAM_BOT_TOKEN") or getattr(config, 'TELEGRAM_BOT_TOKEN', None)
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")   or getattr(config, 'TELEGRAM_CHAT_ID',   None)
    if not token or not chat_id:
        logging.error(
            "❌ توکن یا Chat ID تلگرام تنظیم نشده است. "
            f"TOKEN موجود={bool(token)} | CHAT_ID موجود={bool(chat_id)}"
        )
        return False

    logging.info(f"📤 در حال ارسال پیام تلگرام (chat_id={chat_id[:4]}***، طول متن={len(text)})...")

    url     = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    proxy   = get_proxy()

    for attempt in range(1, max_retries + 1):
        try:
            response = session.post(
                url, json=payload, timeout=15,
                proxies={"https": proxy} if proxy else None,
            )
            response.raise_for_status()
            logging.info(f"✅ پیام تلگرام با موفقیت ارسال شد (status={response.status_code}).")
            return True
        except Exception as e:
            # ✅ جزئیات دقیق‌تر خطا — مخصوصاً بدنه‌ی پاسخ تلگرام (اگر خطای HTTP باشد)
            resp_detail = ""
            resp = getattr(e, 'response', None)
            if resp is not None:
                try:
                    resp_detail = f" | پاسخ سرور: {resp.text[:300]}"
                except Exception:
                    pass
            logging.warning(f"⚠️ تلاش {attempt}/{max_retries} ارسال تلگرام ناموفق: {e}{resp_detail}")
            if attempt < max_retries:
                time.sleep(2 * attempt)

    logging.error("❌ ارسال پیام تلگرام بعد از تمام تلاش‌ها ناموفق بود — سیگنال ممکن است گم شود.")
    return False


def format_and_send_signal(signal_data):
    """ارسال سیگنال هوشمند سیستم v8.3"""
    d = signal_data
    icon       = "🟢 #LONG" if d.get('direction') == "LONG" else "🔴 #SHORT"
    raw_pair   = d.get('pair') or d.get('pair_display') or 'UNKNOWN'
    clean_pair = str(raw_pair).replace('_', '/')

    try:
        sl_dist  = abs(float(d['entry_price']) - float(d['stop_loss']))
        tp_dist  = abs(float(d['tp2'])         - float(d['entry_price']))
        rr_ratio = round(tp_dist / sl_dist, 1) if sl_dist > 0 else 0
    except Exception:
        rr_ratio = 0

    # ✅ FIX: ADX=0 یک مقدار معتبر است — دیگر با adx_score جایگزین نمی‌شود
    _adx_raw = d.get('feat_adx')
    adx_val  = _adx_raw if _adx_raw is not None else d.get('adx_score', 0)

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
        f"🧠 <i>وضعیت: تایید شده توسط مدل اختصاصی {clean_pair}</i>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>این یک سیگنال است، نه یک معامله‌ی اجراشده. ربات به‌صورت "
        f"خودکار سفارشی در صرافی ثبت نمی‌کند.</i>"
    )
    send_telegram_message(message)


def format_and_send_momentum_signal(signal: dict):
    """
    سیگنال استراتژی Daily Momentum (BTC/ETH، نگه‌داری ثابت ~۵ روزه، بدون SL).
    فرمت متفاوت از سیگنال TA چهارساعته چون این پوزیشن روزهای متوالی نگه
    داشته می‌شود، نه با SL/TP لحظه‌ای.
    """
    icon = "🟢 #LONG" if signal.get('direction') == "LONG" else "🔴 #SHORT"
    pair = str(signal.get('pair', 'UNKNOWN')).replace('_', '/')
    mom_ret = signal.get('momentum_return_pct', 0)

    message = (
        f"<b>{icon} سیگنال Momentum روزانه</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 <b>جفت ارز:</b> <code>{pair}</code>\n"
        f"💵 <b>قیمت ورود:</b> <code>{signal.get('entry_price')}</code>\n"
        f"📈 <b>بازده {signal.get('lookback_days')} روز اخیر:</b> <code>{mom_ret:+.2f}%</code>\n"
        f"📅 <b>تاریخ ورود:</b> <code>{signal.get('entry_date')}</code>\n"
        f"⏳ <b>تاریخ خروج برنامه‌ریزی‌شده:</b> <code>{signal.get('planned_exit_date')}</code> "
        f"(~{signal.get('hold_days')} روز)\n"
        f"━━━━━━━━━━━━━━━\n"
        f"⚠️ <i>این استراتژی بدون Stop-Loss طراحی شده — نگه‌داری ثابت "
        f"{signal.get('hold_days')} روزه، دقیقاً طبق نسخه‌ی تست‌شده. "
        f"ریسک این دوره را خودت مدیریت کن (مثلاً سایز پوزیشن کوچک‌تر).</i>\n"
        f"🔬 <i>مبتنی بر شواهد walk-forward؛ edge وابسته به رژیم بازار است "
        f"(در بازار رنج ممکن است ضرر بدهد).</i>"
    )
    send_telegram_message(message)


def send_momentum_exit_notice(pair: str, direction: str, entry_price: float,
                               close_price: float, pnl_percent: float,
                               entry_date, close_date):
    icon = "✅" if pnl_percent > 0 else "🔻"
    message = (
        f"<b>{icon} بسته شدن پوزیشن Momentum</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🪙 <b>جفت ارز:</b> <code>{str(pair).replace('_', '/')}</code>\n"
        f"↕️ <b>جهت:</b> <code>{direction}</code>\n"
        f"📅 <b>ورود:</b> <code>{entry_date}</code> @ <code>{entry_price}</code>\n"
        f"📅 <b>خروج:</b> <code>{close_date}</code> @ <code>{close_price}</code>\n"
        f"📊 <b>PnL:</b> <code>{pnl_percent:+.2f}%</code>\n"
    )
    send_telegram_message(message)


def send_heartbeat_report(watchlist_count, model_count):
    message = (
        f"🤖 <b>Status: System Online (Signal-Only Mode)</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🌐 <b>واچ‌لیست فعال:</b> <code>{watchlist_count} ارز</code>\n"
        f"🧠 <b>مدل‌های هوش مصنوعی فعال:</b> <code>{model_count}</code>\n"
        f"⏳ <b>وضعیت شبکه:</b> <code>Stable (OK)</code>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<i>ربات در حال رصد دقیق بازار است...</i>"
    )
    send_telegram_message(message)
