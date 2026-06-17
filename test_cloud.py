from src import database
try:
    with database.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        print("✅ اتصال ابری موفق:", cursor.fetchone())
except Exception as e:
    print("❌ خطای اتصال:", e)
