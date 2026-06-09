import os
try:
    os.makedirs("data", exist_ok=True)
    with open("data/test_file.txt", "w") as f:
        f.write("test")
    print("✅ دسترسی نوشتن وجود دارد و پوشه ساخته شد.")
except Exception as e:
    print(f"❌ خطا در دسترسی: {e}")
