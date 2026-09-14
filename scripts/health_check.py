import sys
import os
import sqlite3
import time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(PROJECT_DIR, "bot.db")
LOG_FILE = os.path.join(PROJECT_DIR, "logs", "bot.info.log")

def check_db():
    if not os.path.exists(DB_FILE):
        print("[FAIL] Database not found:", DB_FILE)
        return False
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("SELECT 1")
        conn.close()
        print("DB: OK")
        return True
    except Exception as e:
        print(f"[FAIL] DB error: {e}")
        return False

def check_log():
    if not os.path.exists(LOG_FILE):
        print("[FAIL] Log file not found:", LOG_FILE)
        return False
    age = time.time() - os.path.getmtime(LOG_FILE)
    if age > 600:
        print(f"[FAIL] Log too old: {age:.0f}s")
        return False
    print("LOG: OK")
    return True

if __name__ == "__main__":
    ok = True
    if not check_db():
        ok = False
    if not check_log():
        ok = False
    if ok:
        print("[OK] All checks passed")
        sys.exit(0)
    else:
        sys.exit(1)