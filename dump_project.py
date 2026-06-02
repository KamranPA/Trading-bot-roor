import os

# لیست پوشه‌ها یا فایل‌هایی که می‌خواهی نادیده گرفته شوند
IGNORED_DIRS = ['.git', '__pycache__', 'data', '.github']
IGNORED_FILES = ['trading_bot.db', 'dump_project.py']
# پسوندهای متنی مجاز برای کپی شدن
VALID_EXTENSIONS = ['.py', '.json', '.txt', '.yml', '.yaml', '.md']

def merge_project_files(output_filename="all_project_files.txt"):
    root_dir = os.path.dirname(os.path.abspath(__file__))
    
    with open(output_filename, "w", encoding="utf-8") as outfile:
        outfile.write(f"=== ARCHIVE OF PROJECT: {os.path.basename(root_dir)} ===\n")
        outfile.write(f"Generated on: {os.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        outfile.write("="*50 + "\n\n")
        
        for root, dirs, files in os.walk(root_dir):
            # فیلتر کردن پوشه‌های نادیده گرفته شده
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            
            for file in files:
                if file in IGNORED_FILES:
                    continue
                    
                file_path = os.path.join(root, file)
                relative_path = os.path.relpath(file_path, root_dir)
                
                # بررسی پسوند فایل
                _, ext = os.path.splitext(file)
                if ext.lower() in VALID_EXTENSIONS:
                    try:
                        with open(file_path, "r", encoding="utf-8") as infile:
                            content = infile.read()
                            
                            # ساختار تفکیک‌کننده برای خوانایی بهتر
                            outfile.write(f"📁 FILE: {relative_path}\n")
                            outfile.write("-" * len(f"FILE: {relative_path}") + "\n")
                            outfile.write(content)
                            outfile.write("\n\n" + "="*80 + "\n\n")
                            print(f"✅ کپی شد: {relative_path}")
                    except Exception as e:
                        print(f"⚠️ خطای خواندن فایل {relative_path}: {e}")

if __name__ == "__main__":
    merge_project_files()
