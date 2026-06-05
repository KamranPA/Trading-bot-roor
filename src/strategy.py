# src/strategy.py - اصلاح شده

def check_swing_high(df, index, window):
    if index < window or index >= len(df) - window:
        return False
    current_high = df.loc[index, 'High']
    for i in range(1, window + 1):
        if df.loc[index - i, 'High'] > current_high or df.loc[index + i, 'High'] > current_high:
            return False
    return True

def check_swing_low(df, index, window):
    if index < window or index >= len(df) - window:
        return False
    current_low = df.loc[index, 'Low']
    for i in range(1, window + 1):
        if df.loc[index - i, 'Low'] < current_low or df.loc[index + i, 'Low'] < current_low:
            return False
    return True
