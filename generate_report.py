import sqlite3
import config

def generate_report():
    db_path = config.DB_PATH_BACKTEST
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    report_lines = ["📈 گزارش بکتست Breakout", "================================"]
    total_trades_all = 0
    
    for symbol in config.WATCHLIST:
        cursor.execute("SELECT COUNT(*), AVG(pnl_percent > 0) * 100 FROM signals WHERE symbol = ?", (symbol,))
        row = cursor.fetchone()
        if row and row[0] > 0:
            count, win_rate = row
            report_lines.append(f"{symbol} | نرخ برد: {win_rate:.1f} | تعداد معاملات: {count}")
            total_trades_all += count
            
    report_lines.append("================================")
    report_lines.append(f"📊 مجموع معاملات: {total_trades_all}")
    
    with open("backtest_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    conn.close()

if __name__ == "__main__":
    generate_report()
