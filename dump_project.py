#dump_project.py

import os
from datetime import datetime
from pathlib import Path

# استفاده از set برای سرعت بالاتر در جستجو
IGNORED_DIRS = {'.git', '__pycache__', 'data', '.github', 'src/models'}
IGNORED_FILES = {'trading_bot.db', 'dump_project.py', 'all_project_files.txt'}
VALID_EXTENSIONS = {'.py', '.json', '.txt', '.yml', '.yaml', '.md'}

def merge_project_files(output_filename="all_project_files.txt"):
    root_dir = Path(__file__).parent.resolve()
    
    with open(output_filename, "w", encoding="utf-8") as outfile:
        # نوشتن سربرگ پروژه
        outfile.write(f"=== ARCHIVE OF PROJECT: {root_dir.name} ===\n")
        outfile.write(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        outfile.write("="*50 + "\n\n")
        
        # پیمایش فایل‌ها
        for file_path in root_dir.rglob('*'):
            # بررسی فیلترها
            if any(part in IGNORED_DIRS for part in file_path.parts):
                continue
            if file_path.name in IGNORED_FILES or not file_path.is_file():
                continue
            if file_path.suffix.lower() not in VALID_EXTENSIONS:
                continue
                
            try:
                relative_path = file_path.relative_to(root_dir)
                content = file_path.read_text(encoding="utf-8")
                
                outfile.write(f"📁 FILE: {relative_path}\n")
                outfile.write("-" * (len(str(relative_path)) + 8) + "\n")
                outfile.write(content)
                outfile.write("\n\n" + "="*80 + "\n\n")
                print(f"✅ پردازش شد: {relative_path}")
            except Exception as e:
                print(f"⚠️ خطای خواندن فایل {file_path.name}: {e}")

if __name__ == "__main__":
    merge_project_files()
    print(f"\n🚀 آرشیو نهایی با موفقیت در 'all_project_files.txt' ایجاد شد.")
