def save_signal_advanced(pair, direction, entry_price, stop_loss, tp1, tp2, position_size, **features):
    """ذخیره سیگنال با ۹ فیچر استاندارد و فیلتر کردن مقادیر اضافی"""
    with sqlite3.connect(config.DB_NAME) as conn:
        cursor = conn.cursor()
        
        # لیست دقیق فیچرهایی که در دیتابیس تعریف کردیم
        allowed_features = [
            'feat_adx', 'feat_vol_ratio', 'feat_atr_percent', 'feat_rsi', 
            'feat_trend_line', 'feat_ema_deviation', 'feat_rsi_momentum', 
            'feat_body_ratio', 'feat_high_volume_session'
        ]
        
        # استخراج مقادیر فیچرها (اگر در دیکشنری نبودند، مقدار 0.0 لحاظ می‌شود)
        values = [features.get(f, 0.0) for f in allowed_features]
        
        # دستور درج (Insert) به تعدادِ ستون‌های صحیح
        query = f"""
            INSERT INTO signals (
                timestamp, symbol, direction, entry_price, stop_loss, 
                {', '.join(allowed_features)}
            ) VALUES (?, ?, ?, ?, ?, {', '.join(['?'] * len(allowed_features))})
        """
        
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(query, [timestamp, pair, direction, entry_price, stop_loss] + values)
        
        # ذخیره تارگت‌ها (اگر نیاز است)
        signal_id = cursor.lastrowid
        cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, 1, ?)", (signal_id, tp1))
        cursor.execute("INSERT INTO signal_targets (signal_id, target_number, target_price) VALUES (?, 2, ?)", (signal_id, tp2))
        
        conn.commit()
