# ---------------------------------------------------------
# FILE PATH: test_telegram.py (تست شبیه‌سازی خط لوله تلگرام)
# ---------------------------------------------------------
import os
import sys
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    from src import telegram_bot
    import config
except ImportError as e:
    print(f"❌ خطای ایمپورت: {e}")
    sys.exit(1)

def run_fake_signal_test():
    logging.info("⚡ در حال ساخت سیگنال شبیه‌سازی شده برای تست لوله تلگرام...")
    
    # ایجاد یک دیکشنری سیگنال فرضی دقیقاً با فرمتی که استراتژی تولید می‌کند
    fake_signal = {
        'pair_display': 'BTC/USDT (TEST)',
        'direction': 'LONG',
        'entry_price': 65250.0,
        'stop_loss': 64100.0,
        'tp1': 65850.0,
        'tp2': 66900.0,
        'position_size': 250.0,
        'feat_rsi': 58.4,
        'feat_adx': 28.2,
        'feat_atr_percent': 1.5
    }
    
    try:
        # شلیک سیگنال به ماژول تلگرام شما
        telegram_bot.format_and_send_signal(fake_signal)
        print("\n🟢 بوم! اگر توکن و چت‌آیدی درست باشند، پیام باید الان در تلگرام شما باشد.")
    except Exception as e:
        print(f"\n🔴 خطا! ارسال پیام به تلگرام شکست خورد: {e}")

if __name__ == "__main__":
    run_fake_signal_test()
