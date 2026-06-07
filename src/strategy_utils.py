# ---------------------------------------------------------
# FILE PATH: /src/strategy_utils.py
# ---------------------------------------------------------

def find_last_swing(df, level_type, window):
    """
    جستجوی آخرین سطح Swing High یا Swing Low در دیتافریم
    level_type: 'high' یا 'low'
    window: تعداد کندل‌های اطراف برای تایید قله یا دره
    """
    # جستجو از آخرین کندل به سمت عقب (بدون در نظر گرفتن کندل آخر برای جلوگیری از سیگنال لحظه‌ای فیک)
    for i in range(len(df) - 2, window, -1):
        if level_type == 'high':
            # بررسی اینکه آیا کندل i از همه کندل‌های اطراف بزرگتر است؟
            if (df.loc[i, 'High'] > df.loc[i-window:i, 'High'].max()) and \
               (df.loc[i, 'High'] > df.loc[i:i+window, 'High'].max()):
                return float(df.loc[i, 'High'])
        
        elif level_type == 'low':
            # بررسی اینکه آیا کندل i از همه کندل‌های اطراف کوچکتر است؟
            if (df.loc[i, 'Low'] < df.loc[i-window:i, 'Low'].min()) and \
               (df.loc[i, 'Low'] < df.loc[i:i+window, 'Low'].min()):
                return float(df.loc[i, 'Low'])
    
    return None
