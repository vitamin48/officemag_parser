"""
Шаг 3. Сбор детальной информации о товарах (финальная версия с обработкой 404).
- Устойчив к падениям браузера.
- Периодически перезапускает браузер для предотвращения утечек памяти.
- Корректно обрабатывает несуществующие страницы (404).
- В случае сбоя ждет 5 минут и пытается продолжить.
"""
import os
import time
import datetime
import json
import random
import re
import requests
import platform
import socket
from playwright.sync_api import sync_playwright, TimeoutError, Page
from tqdm import tqdm
from colorama import init, Fore, Style

# Попытка импортировать секретные данные
try:
    from config import BOT_TOKEN, CHAT_ID
except ImportError:
    BOT_TOKEN, CHAT_ID = None, None

# --- НАСТРОЙКИ СКРИПТА ---
INPUT_URL_FILE = os.path.join("in", "product_links.txt")
OUTPUT_JSON_FILE = os.path.join("out", "products_data.json")
OUTPUT_FAILED_FILE = os.path.join("out", "failed_urls.txt")
DEBUG_DIR = os.path.join("out", "debug")

LOGIN_URL = "https://www.officemag.ru/auth/"
USER_LOGIN = "forvk180420@gmail.com"
USER_PASSWORD = "forvk180420"

BASE_URL = "https://www.officemag.ru"

HEADLESS_MODE = False
TIMEOUT = 45000
MAX_RETRIES = 2
PAUSE_BETWEEN_REQUESTS = (2, 6)
RESTART_BROWSER_EVERY_N_URLS = 350
CRASH_RECOVERY_WAIT_SECONDS = 300


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (без изменений) ---
def send_logs_to_telegram(message: str):
    BOT_TOKEN = '6456958617:AAEhKxpvbWxeDoq7IPf7fQo0sxbQ_LqSVz0'
    CHAT_ID = '128592002'
    if not BOT_TOKEN or not CHAT_ID:
        print(Fore.YELLOW + "ПРЕДУПРЕЖДЕНИЕ: BOT_TOKEN или CHAT_ID не заданы. Уведомление не отправлено.")
        return
    try:
        platform_info = platform.system()
        hostname = socket.gethostname()
        user = os.getlogin()
        full_message = message + f'\n\n---\n🖥️ {platform_info}\n👤 {hostname}\\{user}'
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        data = {"chat_id": CHAT_ID, "text": full_message}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(Fore.RED + f"Критическая ошибка при отправке в Telegram: {e}")


def save_debug_info(page: Page, article_id: str):
    print(Fore.MAGENTA + f"!!! Сохраняю отладочную информацию для артикула {article_id}...")
    os.makedirs(DEBUG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.png")
    html_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(Fore.MAGENTA + f"  - Скриншот сохранен: {screenshot_path}")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())
        print(Fore.MAGENTA + f"  - HTML-код сохранен: {html_path}")
    except Exception as e:
        print(Fore.RED + f"  - Не удалось сохранить отладочную информацию: {e}")


def read_simple_urls(filepath: str) -> list[str]:
    if not os.path.exists(filepath):
        print(Fore.YELLOW + f"ОШИБКА: Входной файл не найден: {filepath}")
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip().startswith('http')]
    unique_urls = list(dict.fromkeys(urls))
    print(f"Загружено {Fore.GREEN}{len(unique_urls)}{Style.RESET_ALL} уникальных ссылок для обработки из {filepath}.")
    return unique_urls


def load_existing_data(filepath: str) -> dict:
    if not os.path.exists(filepath): return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            print(f"Загружено {Fore.GREEN}{len(data)}{Style.RESET_ALL} уже собранных товаров из JSON.")
            return data
        except json.JSONDecodeError:
            print(Fore.YELLOW + f"ПРЕДУПРЕЖДЕНИЕ: JSON-файл {filepath} поврежден. Начинаем с нуля.")
            return {}


def save_json_data(data: dict, filepath: str):
    output_dir = os.path.dirname(filepath)
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_failed_url(url: str, reason: str, filepath: str):
    output_dir = os.path.dirname(filepath)
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | {reason} | {url}\n")


def perform_login(page: Page):
    print("Выполняю авторизацию...")
    try:
        page.goto(LOGIN_URL)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(3)
        page.keyboard.press("Escape")
        time.sleep(1)
        page.get_by_label("Электронная почта или логин").fill(USER_LOGIN)
        page.get_by_label("Пароль").fill(USER_PASSWORD)
        page.get_by_role("button", name="Войти").click()
        page.wait_for_selector("span.User__trigger:has-text('Кабинет')", timeout=15000)
        print(Fore.GREEN + "Авторизация прошла успешно.")
        return True
    except Exception as e:
        print(Fore.RED + f"ОШИБКА во время авторизации: {e}")
        send_logs_to_telegram(f"🔴 ОШИБКА АВТОРИЗАЦИИ!\n\nСкрипт не смог войти в аккаунт.\nОшибка: {e}")
        return False


def parse_product_page(page: Page) -> dict:
    product_container_selector = "div.itemInfo.group"
    page.wait_for_selector(product_container_selector, timeout=25000)
    container = page.locator(product_container_selector)
    ga_data_locator = container.locator(".itemInfoDetails[data-ga-object]")
    if ga_data_locator.count() == 0: raise ValueError("Не найден основной JSON-блок данных (data-ga-object)")
    ga_data_str = ga_data_locator.get_attribute("data-ga-object")
    ga_data = json.loads(ga_data_str)
    item_info = ga_data["items"][0]
    item_id = item_info.get("item_id")
    brand = item_info.get("item_brand", "N/A")
    price = float(item_info.get("price", 0.0))
    article = f"goods_{item_id}"
    name_selector = "div.ProductHead__name, h1.ProductHead__name"
    name = container.locator(name_selector).first.inner_text().strip()
    description_locator = container.locator(".infoDescription__full")
    description = description_locator.inner_text().strip() if description_locator.count() > 0 else ""
    characteristics = {}
    if container.locator("ul.infoFeatures li.specTitle:has-text('Характеристики')").count() > 0:
        char_elements = container.locator("ul.infoFeatures li:not(.specTitle)").all()
        for li in char_elements:
            text = li.inner_text().strip()
            parts = re.split(r'\s+[—:]\s+', text, maxsplit=1)
            if len(parts) == 2: characteristics[parts[0].strip()] = parts[1].strip()
    stocks = {}
    stock_rows = page.locator("tr.AvailabilityItem").all()
    for row in stock_rows:
        store_name_locator = row.locator(".AvailabilityLabel")
        if not store_name_locator.count(): continue
        store_name = store_name_locator.inner_text().strip()
        amount_locator = row.locator(".AvailabilityBox--green")
        amount = amount_locator.inner_text().strip() if amount_locator.count() > 0 else "0"
        stocks[store_name] = amount
    image_urls = set()
    image_locators = container.locator(".ProductPhotoThumb__link").all()
    if image_locators:
        for thumb in image_locators:
            href = thumb.get_attribute('href')
            if href and href.startswith('https://s3.ibta.ru'): image_urls.add(href)
    else:
        main_image_locator = container.locator(".itemInfoPhotos__link")
        if main_image_locator.count() > 0:
            href = main_image_locator.get_attribute('href')
            if href and href.startswith('https://s3.ibta.ru'): image_urls.add(href)
    order_block_selector = container.locator("div.order")
    red_status_locator = order_block_selector.locator(".ProductState--red")
    if red_status_locator.count() > 0:
        status_text = red_status_locator.first.inner_text().strip()
        if "Недоступен" in status_text or "Есть только в другом сочетании" in status_text:
            raise ValueError(f"Товар недоступен: {status_text}")
        if "Выведен" in status_text: raise ValueError("Товар выведен из ассортимента")
    return {"name": name, "price": price, "brand": brand, "stocks": stocks, "description": description,
            "characteristics": characteristics, "image_urls": list(image_urls), "product_url": page.url,
            "article_from_page": article, "code": item_id}


# --- ГЛАВНАЯ ФУНКЦИЯ ---
def main():
    init(autoreset=True)
    start_time = datetime.datetime.now()
    start_message = f"🚀 Парсер Officemag (Шаг 3) запущен в {start_time.strftime('%H:%M:%S')}"
    print(Fore.CYAN + start_message)
    # send_logs_to_telegram(start_message)

    try:
        urls_to_parse = read_simple_urls(INPUT_URL_FILE)
        all_data = load_existing_data(OUTPUT_JSON_FILE)
        initial_data_count = len(all_data)

        def get_article_from_url(url: str) -> str | None:
            match = re.search(r'/goods/(\d+)', url)
            if match: return f"goods_{match.group(1)}"
            return None

        urls_to_process = [url for url in urls_to_parse if
                           (article := get_article_from_url(url)) and article not in all_data]

        if not urls_to_process:
            print(Fore.YELLOW + "Все товары из списка уже обработаны. Завершение работы.")
            send_logs_to_telegram("✅ Все товары уже обработаны. Новых ссылок нет.")
            return

        print(f"К обработке {Fore.CYAN}{len(urls_to_process)}{Style.RESET_ALL} новых ссылок.")

        with sync_playwright() as p:
            browser, context, page = None, None, None

            def launch_browser():
                nonlocal browser, context, page
                if browser:
                    try:
                        browser.close()
                    except Exception as e:
                        print(Fore.YELLOW + f"Не удалось корректно закрыть браузер: {e}")

                print(Fore.CYAN + "\n--- Запускаю новый экземпляр браузера ---")
                browser = p.chromium.launch(headless=HEADLESS_MODE, args=["--disable-dev-shm-usage"])
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")
                context.set_default_timeout(TIMEOUT)
                page = context.new_page()

                if not perform_login(page):
                    raise RuntimeError("Не удалось авторизоваться, дальнейшая работа невозможна.")

            launch_browser()

            for i, url in enumerate(tqdm(urls_to_process, desc="Сбор данных о товарах")):
                if i > 0 and i % RESTART_BROWSER_EVERY_N_URLS == 0:
                    print(Fore.CYAN + f"\nОбработано {i} ссылок. Плановый перезапуск браузера...")
                    launch_browser()

                article_id_from_url = get_article_from_url(url)
                if not article_id_from_url:
                    log_failed_url(url, "Некорректный URL", OUTPUT_FAILED_FILE)
                    continue

                product_data = None
                for attempt in range(MAX_RETRIES):
                    try:
                        page.goto(url, wait_until="domcontentloaded")

                        # ====================================================================
                        # ИЗМЕНЕНИЕ: Проверяем на 404 страницу ПЕРЕД парсингом
                        # ====================================================================
                        not_found_locator = page.locator(".Blank__header:has-text('Страница не найдена')")
                        if not_found_locator.count() > 0:
                            print(Fore.YELLOW + f"  - Страница не найдена (404). Пропускаю.")
                            log_failed_url(url, "Страница не найдена (404)", OUTPUT_FAILED_FILE)
                            # Устанавливаем product_data в специальное значение, чтобы не было повторных попыток
                            product_data = "SKIP"
                            break

                        page.evaluate(
                            "() => { const chat = document.querySelector('.online-chat-root-TalkMe'); if (chat) chat.remove(); }")
                        product_data = parse_product_page(page)

                        if product_data:
                            break
                    except Exception as e:
                        error_text = str(e)
                        print(Fore.RED + f"\n  [Попытка {attempt + 1}] ОШИБКА: {error_text[:200]}")

                        if "crashed" in error_text.lower():
                            print(Fore.RED + Style.BRIGHT + "!!! ОБНАРУЖЕНО ПАДЕНИЕ СТРАНИЦЫ !!!")
                            send_logs_to_telegram(
                                f"🟡 ВНИМАНИЕ: Страница упала (crashed). Перезапускаю браузер через {CRASH_RECOVERY_WAIT_SECONDS} сек.")
                            time.sleep(CRASH_RECOVERY_WAIT_SECONDS)
                            launch_browser()
                            continue

                        debug_id = f"{article_id_from_url}_attempt_{attempt + 1}"
                        save_debug_info(page, debug_id)

                        if attempt < MAX_RETRIES - 1:
                            print(Style.DIM + "  -> Пауза перед следующей попыткой...")
                            time.sleep(10)

                if product_data and product_data != "SKIP":
                    all_data[article_id_from_url] = product_data
                    save_json_data(all_data, OUTPUT_JSON_FILE)
                elif product_data is None:  # Только если все попытки провалились
                    print(Fore.RED + Style.BRIGHT + f"!!! НЕ УДАЛОСЬ обработать {url} после {MAX_RETRIES} попыток.")
                    if not any(url in line for line in
                               (open(OUTPUT_FAILED_FILE).readlines() if os.path.exists(OUTPUT_FAILED_FILE) else [])):
                        log_failed_url(url, "Не удалось загрузить или спарсить", OUTPUT_FAILED_FILE)

                time.sleep(random.uniform(*PAUSE_BETWEEN_REQUESTS))

            browser.close()

        end_time = datetime.datetime.now()
        duration = end_time - start_time
        newly_added_count = len(all_data) - initial_data_count

        finish_message = (
            f"✅ Парсер успешно завершил работу.\n\n"
            f"👍 Добавлено новых товаров: {newly_added_count}\n"
            f"💾 Всего товаров в базе: {len(all_data)}\n"
            f"🕒 Время выполнения: {str(duration).split('.')[0]}"
        )
        print("-" * 50)
        print(Fore.CYAN + finish_message)
        send_logs_to_telegram(finish_message)

    except Exception as e:
        error_message = f"❌ КРИТИЧЕСКАЯ ОШИБКА в парсере!\n\nСкрипт аварийно завершился.\n\nОшибка:\n{e}"
        print(Fore.RED + Style.BRIGHT + error_message)
        send_logs_to_telegram(error_message)


if __name__ == '__main__':
    main()
