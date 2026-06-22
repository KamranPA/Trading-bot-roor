import sys
sys.path.insert(0, '.')
from src.database import _db
try:
    with _db() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO scan_log (pair, status, total_score) VALUES ('TEST', 'test', 0)")
    print('✅ نوشتن در دیتابیس موفق بود')
except Exception as e:
    print(f'❌ خطا: {e}')
    sys.exit(1)
