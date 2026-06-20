# 🤖 Trading Bot

ربات معاملاتی خودکار بر پایه استراتژی Swing Breakout با هوش مصنوعی LightGBM.
داده‌ها از Yahoo Finance دریافت می‌شوند، پوزیشن‌ها در Supabase (PostgreSQL) ثبت می‌شوند و سیگنال‌ها از طریق تلگرام ارسال می‌شوند.

---

## ساختار پروژه

```
├── config.py                   # تنظیمات مرکزی (WATCHLIST، وزن‌ها، پارامترها)
├── fetcher.py                  # دریافت داده تاریخی از Yahoo Finance → data/4h/
├── main.py                     # حلقه اصلی ربات لایو
├── analyze_losses.py           # آنالیز معاملات ضررده
├── best_params.json            # بهترین پارامترها (خروجی optimizer)
├── backtest_table_summary.csv  # خلاصه نتایج بکتست به تفکیک ارز
│
├── data/
│   ├── 4h/                     # داده تاریخی هر ارز (SYMBOL_history.csv)
│   ├── backtest_trades.csv     # معاملات بکتست (ورودی آموزش مدل AI)
│   └── trading_bot_backtest.db # خروجی SQLite بکتست (GitHub Artifacts)
│
└── src/
    ├── backtester.py           # موتور بکتست (بدون Look-Ahead Bias)
    ├── optimizer.py            # بهینه‌سازی پارامترها با Grid Search
    ├── train_model.py          # آموزش مدل AI (بکتست اول، لایو دوم)
    ├── brain.py                # مدیریت مدل‌های pkl و پیش‌بینی
    ├── strategy.py             # منطق تولید سیگنال لایو
    ├── strategy_utils.py       # توابع کمکی (Swing High/Low)
    ├── indicators.py           # اندیکاتورها (ADX، RSI، EMA، ATR)
    ├── database.py             # اتصال PostgreSQL و CRUD سیگنال‌ها
    ├── csv_store.py            # ذخیره و خواندن معاملات بکتست
    ├── telegram_bot.py         # ارسال پیام تلگرام
    └── models/                 # مدل‌های pkl هر ارز (SYMBOL_model.pkl)
```

---

## پیپلاین کامل

```
fetcher.py       ← دریافت داده ۴ ساعته از Yahoo Finance
      ↓
backtester.py    ← بکتست + ذخیره فیچرها در data/backtest_trades.csv
      ↓
optimizer.py     ← بهینه‌سازی پارامترها ← best_params.json
      ↓
train_model.py   ← آموزش LightGBM (اول بکتست، بعد داده لایو)
      ↓
main.py          ← اجرای ربات لایو با مدل آموزش‌دیده
```

---

## متغیرهای محیطی

| متغیر | توضیح |
|---|---|
| `DATABASE_URL` | رشته اتصال PostgreSQL (Supabase) |
| `TELEGRAM_BOT_TOKEN` | توکن ربات تلگرام |
| `TELEGRAM_CHAT_ID` | شناسه چت تلگرام |

---

## تنظیمات اصلی (`config.py`)

| پارامتر | مقدار پیش‌فرض | توضیح |
|---|---|---|
| `WATCHLIST` | ۱۱ ارز | لیست ارزهای تحت نظر |
| `TIMEFRAME` | `4h` | تایم‌فریم معاملاتی |
| `ADX_THRESHOLD` | `15.0` | حداقل قدرت روند برای ورود |
| `TP_RATIO` | `1.5` | نسبت حد سود به حد ضرر |
| `SL_RATIO` | `1.0` | ضریب فاصله حد ضرر |
| `MAX_OPEN_POSITIONS` | `3` | حداکثر پوزیشن‌های همزمان |
| `MIN_REQUIRED_SCORE` | `60` | حداقل امتیاز کل برای ورود |
| `AI_THRESHOLD` | `65.0` | حداقل امتیاز AI برای تأیید |
| `WEIGHT_AI` | `40` | وزن امتیاز هوش مصنوعی |
| `WEIGHT_ADX` | `20` | وزن امتیاز ADX |
| `WEIGHT_RSI` | `20` | وزن امتیاز RSI |
| `WEIGHT_EMA` | `20` | وزن امتیاز EMA |

---

## GitHub Actions Workflows

| Workflow | فایل | عملکرد |
|---|---|---|
| **Backtester** | `run_backtester.yml` | fetch → backtest → optimize → train → commit |
| **Bot** | `run_bot.yml` | اجرای ربات لایو |
| **Analyzer** | `analyze.yml` | آنالیز ضررها |
| **Monthly Brain** | `monthly_brain.yml` | بازآموزش ماهانه مدل |
| **Optimizer** | `Optimizer.yml` | بهینه‌سازی مستقل پارامترها |
| **Test DB** | `Test_db.yml` | تست اتصال دیتابیس |

---

## منطق آموزش مدل AI

مدل LightGBM برای هر ارز جداگانه آموزش می‌بیند.

**اولویت منابع داده:**
1. `data/backtest_trades.csv` — منبع اصلی (هزاران معامله تاریخی)
2. PostgreSQL لایو — تکمیل‌کننده (معاملات واقعی ربات)

**فیچرهای ورودی مدل:**
```
feat_adx، feat_atr_percent، feat_rsi، feat_trend_line،
feat_ema_deviation، feat_rsi_momentum، feat_body_ratio
```

**برچسب هدف:** `1` = سودده، `0` = ضررده

---

## خروجی‌های Workflow بکتست

پس از اجرای `run_backtester.yml` سه فایل commit و upload می‌شوند:

| فایل | محتوا |
|---|---|
| `backtest_table_summary.csv` | خلاصه عملکرد هر ارز |
| `best_params.json` | بهترین پارامترهای یافت‌شده |
| `data/trading_bot_backtest.db` | دیتابیس SQLite کامل معاملات |

---

## نکات مهم

- **DOT، LINK، LTC، BCH:** گاهی Yahoo Finance داده برنمی‌گرداند — workflow بقیه را پردازش می‌کند.
- **حداقل داده بکتست:** هر ارز باید حداقل ۲۱۰ کندل ۴ ساعته داشته باشد.
- **حداقل داده آموزش مدل:** حداقل ۳۰ معامله بسته‌شده با نتایج متنوع (سود و ضرر).
- **وضعیت‌های معامله در بکتست:** `SL_HIT`، `TP_HIT`، `EXPIRED`
- **وضعیت‌های معامله در لایو:** `SL_HIT`، `TP_HIT`، `CLOSED`
