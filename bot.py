import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
URL_TO_CHECK = os.getenv("URL_TO_CHECK")

CHECK_INTERVAL = 900  # 15 хвилин


def send_telegram_message(chat_id, message):
    """Відправляє повідомлення у чат"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Помилка надсилання: {e}")

def get_page_content():
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        response = requests.get(URL_TO_CHECK, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        links = [a.get('href') for a in soup.find_all('a', href=True) if a.get('href')]
        return soup.get_text(), links
    except Exception as e:
        print(f"Помилка завантаження сайту: {e}")
        return None, None

def get_latest_files():
    """Шукає всі файли у тому порядку, в якому вони йдуть на сторінці (зверху вниз)"""
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    try:
        response = requests.get(URL_TO_CHECK, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        file_extensions = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar')
        found_files = []
        
        ignore_words = ['temy', 'tema','zavdannya','vidpovidi', 'instrukciya', 'polozhennya', 'zrazok', 'template']
        
        for a in soup.find_all('a', href=True):
            href = a.get('href')
            if href and href.lower().endswith(file_extensions):
                if href.startswith('/'):
                    parsed_url = urlparse(URL_TO_CHECK)
                    base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
                    href = base_domain + href
                
                file_name = a.get_text(strip=True) or href.split('/')[-1]
                lower_text = (file_name + " " + href).lower()
                
                if any(w in lower_text for w in ignore_words):
                    continue
                
                file_item = {"name": file_name, "url": href}
                if file_item not in found_files:
                    found_files.append(file_item)
                
        return found_files
    except Exception as e:
        print(f"Помилка при пошуку файлів: {e}")
        return []

def main():
    print("Бот запущено (з привітанням та автосповіщеннями)...")

    initial_files = get_latest_files()
    known_urls = {f['url'] for f in initial_files}
    
    check_timer = 0
    last_update_id = 0
    active_chats = set()

    while True:
        # 1. Перевіряємо команди від користувачів
        try:
            updates_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=1"
            response = requests.get(updates_url, timeout=2).json()
            
            if response.get("ok"):
                for update in response.get("result", []):
                    last_update_id = update["update_id"]
                    message = update.get("message", {})
                    text = message.get("text", "")
                    chat_id = str(message.get("chat", {}).get("id", ""))
                    
                    if chat_id:
                        active_chats.add(chat_id)
                        
                        # Команда /start
                        if text == "/start":
                            welcome_msg = (
                                "👋 <b>Привіт! Я бот-монітор олімпіадних документів.</b>\n\n"
                                "Я слідкую за сайтом та допомагаю швидко знаходити нові завдання, протоколи й результати.\n\n"
                                "📌 <b>Доступні команди:</b>\n"
                                "• /latest — показати останні 12 файлів зі сторінки\n"
                                "• /check — примусово перевірити, чи є зміни на сайті\n"
                                "• /status — перевірити стан роботи бота\n"
                                "• /start — показати це вікно привітання"
                            )
                            send_telegram_message(chat_id, welcome_msg)
                        
                        elif text == "/status":
                            send_telegram_message(chat_id, "🟢 <b>Бот працює!</b> Моніторю сторінку і готовий надсилати нові файли.")
                        
                        elif text == "/check":
                            send_telegram_message(chat_id, "🔄 <b>Примусова перевірка сайту...</b>")
                            current_files = get_latest_files()
                            current_urls = {f['url'] for f in current_files}
                            new_urls = current_urls - known_urls
                            
                            if new_urls:
                                send_telegram_message(chat_id, f"🚨 <b>Знайдено нові файли ({len(new_urls)})!</b> Використай /latest щоб переглянути.")
                            else:
                                send_telegram_message(chat_id, "✅ Нових файлів на сайтах не з'явилося.")
                        
                        elif text == "/latest":
                            send_telegram_message(chat_id, "📁 Шукаю останні файли...")
                            files = get_latest_files()
                            
                            if not files:
                                send_telegram_message(chat_id, "⚠️ На сторінці не знайдено файлів.")
                            else:
                                latest_slice = files[:12]
                                msg_lines = ["📂 <b>Останні знайдені файли:</b>\n"]
                                for f in latest_slice:
                                    clean_name = f['name'] if len(f['name']) < 60 else f['name'][:57] + "..."
                                    msg_lines.append(f"• <a href='{f['url']}'>{clean_name}</a>")
                                    
                                send_telegram_message(chat_id, "\n".join(msg_lines))

        except Exception as e:
            print(f"Помилка команд: {e}")

        # 2. Таймер планової перевірки (15 хвилин)
        time.sleep(1)
        check_timer += 1

        if check_timer >= CHECK_INTERVAL:
            check_timer = 0
            current_files = get_latest_files()
            
            if current_files:
                current_urls = {f['url'] for f in current_files}
                new_files = [f for f in current_files if f['url'] not in known_urls]
                
                if new_files:
                    print("Знайдено нові файли!")
                    for chat_id in active_chats:
                        for nf in new_files:
                            msg = f"🚨 <b>З'явився новий файл!</b>\n\n• <a href='{nf['url']}'>{nf['name']}</a>"
                            send_telegram_message(chat_id, msg)
                    
                    known_urls = current_urls

if __name__ == "__main__":
    main()
