import sys
import os
import sqlite3
import time
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(PROJECT_DIR, "bot.db")
BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")

def main():
    if not os.path.exists(DB_FILE):
        print(f"[FAIL] Database not found: {DB_FILE}")
        return False

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"bot_{timestamp}.bak")

    print(f"Backing up to: {backup_file}")

    try:
        src = sqlite3.connect(DB_FILE)
        dst = sqlite3.connect(backup_file)
        src.backup(dst)
        dst.close()
        src.close()
        print(f"[OK] Backup created: {backup_file}")
    except Exception as e:
        print(f"[FAIL] Backup failed: {e}")
        return False

    # Cleanup old backups (keep 14)
    backups = sorted(
        [f for f in os.listdir(BACKUP_DIR) if f.startswith("bot_") and f.endswith(".bak")],
        key=lambda f: os.path.getmtime(os.path.join(BACKUP_DIR, f)),
        reverse=True
    )
    for old in backups[14:]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
            print(f"Removed old backup: {old}")
        except Exception as e:
            print(f"[WARN] Failed to remove old backup {old}: {e}")

    print("[OK] Backup completed")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)