import sys, logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
sys.path.insert(0, '.')

import pandas as pd, config
from src.brain import TradingBrain
from src.indicators import TechnicalIndicators

brain = TradingBrain()

# چک کن آیا مدل برای BTC/USDT لود شده
brain_symbol = 'BTC/USDT'
has_model = brain.has_model(brain_symbol)
print(f'مدل برای {brain_symbol} موجود است: {has_model}')

if has_model:
    df = pd.read_csv('data/4h/BTCUSDT_history.csv')
    df_norm = df.rename(columns={c: c.lower() for c in df.columns})
    df_full, _ = TechnicalIndicators.calculate_all_features(df_norm, 'BTCUSDT')

    for i in range(200, 210):
        c = df_full.iloc[i]
        features = {
            'feat_adx':           float(c.get('feat_adx', 0)),
            'feat_atr_percent':   float(c.get('feat_atr_percent', 1.0) or 0),
            'feat_rsi':           float(c.get('feat_rsi', 50)),
            'feat_trend_line':    float(c.get('feat_trend_line', 0)),
            'feat_ema_deviation': abs(float(c.get('feat_ema_deviation', 0))),
            'feat_rsi_momentum':  float(c.get('feat_rsi_momentum', 0)),
            'feat_body_ratio':    float(c.get('feat_body_ratio', 0)),
        }
        try:
            raw = brain.predict_probability(brain_symbol, features)
            ai_score = float(raw)*100 if raw is not None and float(raw)<=1.0 else (float(raw) if raw is not None else None)
            print(f'کندل {i}: raw={raw} ai_score={ai_score}')
        except Exception as e:
            print(f'کندل {i}: خطا - {e}')
else:
    print('⚠️ مدلی برای BTC/USDT لود نشده — model_active باید False باشه')
    print('بررسی همه مدل‌های لود شده:')
    if hasattr(brain, 'models'):
        print(list(brain.models.keys()) if hasattr(brain.models, 'keys') else brain.models)
