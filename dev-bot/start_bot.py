#!/usr/bin/env python3
"""
Скрипт запуска бота с проверкой зависимостей
"""

import os
import sys
import subprocess

def check_dependencies():
    """Проверить установлены ли зависимости"""
    try:
        import telegram
        import requests
        print("✅ All dependencies are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Installing dependencies...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("✅ Dependencies installed successfully")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return False

def main():
    """Основная функция запуска"""
    print("🚀 Starting Monitoring Bot...")
    
    if not check_dependencies():
        sys.exit(1)
    
    # Запускаем бота
    try:
        from bot import main as bot_main
        bot_main()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
