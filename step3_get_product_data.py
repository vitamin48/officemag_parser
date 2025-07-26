"""
Шаг 3. Сбор детальной информации о товарах (финальная версия).

Скрипт считывает список ссылок из файла /in/product_links.txt.
Выполняет авторизацию, затем последовательно обходит каждую ссылку.

... (остальное описание без изменений) ...
"""
import os
import time
import datetime
import json
import random
import re
from playwright.sync_api import sync_playwright, TimeoutError, Page
from tqdm import tqdm

# --- НАСТРОЙКИ СКРИПТА ---
# ИЗМЕНЕНИЕ: Путь к новому входному файлу
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
MAX_RETRIES = 3
PAUSE_BETWEEN_REQUESTS = (2, 5)


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

# ИЗМЕНЕНИЕ: Новая, более простая функция для чтения ссылок
def read_simple_urls(filepath: str) -> list[str]:
    """Загружает ссылки на товары из простого текстового файла."""
    if not os.path.exists(filepath):
        print(f"ОШИБКА: Входной файл не найден: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        # Считываем все непустые строки, которые выглядят как URL
        urls = [line.strip() for line in f if line.strip().startswith('http')]

    # Убираем дубликаты, сохраняя порядок
    unique_urls = list(dict.fromkeys(urls))
    print(f"Загружено {len(unique_urls)} уникальных ссылок для обработки из {filepath}.")
    return unique_urls


def load_existing_data(filepath: str) -> dict:
    if not os.path.exists(filepath): return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            print(f"Загружено {len(data)} уже собранных товаров из JSON.")
            return data
        except json.JSONDecodeError:
            print(f"ПРЕДУПРЕЖДЕНИЕ: JSON-файл {filepath} поврежден. Начинаем с нуля.")
            return {}


# Остальные вспомогательные функции и функция парсинга остаются без изменений
def save_debug_info(page: Page, article_id: str):
    print(f"!!! Сохраняю отладочную информацию для артикула {article_id}...")
    os.makedirs(DEBUG_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.png")
    html_path = os.path.join(DEBUG_DIR, f"{article_id}_{timestamp}_debug.html")
    try:
        page.screenshot(path=screenshot_path, full_page=True)
        print(f"  - Скриншот сохранен: {screenshot_path}")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(page.content())
        print(f"  - HTML-код сохранен: {html_path}")
    except Exception as e:
        print(f"  - Не удалось сохранить отладочную информацию: {e}")


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
        page.keyboard.press("Escape")
        time.sleep(1)
        page.get_by_label("Электронная почта или логин").fill(USER_LOGIN)
        page.get_by_label("Пароль").fill(USER_PASSWORD)
        page.get_by_role("button", name="Войти").click()
        page.wait_for_selector("span.User__trigger:has-text('Кабинет')", timeout=15000)
        print("Авторизация прошла успешно.")
        return True
    except Exception as e:
        print(f"ОШИБКА во время авторизации: {e}")
        return False


def parse_product_page(page: Page) -> dict:
    """
    Извлекает всю информацию с открытой страницы товара.
    Финальная версия, устойчивая к товарам с модификациями и разной верстке.
    """
    product_container_selector = "div.itemInfo.group"
    print(f"  - Жду появления главного контейнера товара ('{product_container_selector}')...")
    page.wait_for_selector(product_container_selector, timeout=25000)
    print("  - Контейнер найден, начинаю сбор данных.")

    container = page.locator(product_container_selector)

    # ====================================================================
    # ИЗМЕНЕНИЕ №1: ЦЕНА, БРЕНД, ID теперь берутся ТОЛЬКО из JSON-атрибута.
    # Это самый надежный источник.
    # ====================================================================
    ga_data_locator = container.locator(".itemInfoDetails[data-ga-object]")
    if ga_data_locator.count() == 0:
        raise ValueError("Не найден основной JSON-блок данных (data-ga-object)")

    ga_data_str = ga_data_locator.get_attribute("data-ga-object")
    ga_data = json.loads(ga_data_str)
    item_info = ga_data["items"][0]

    item_id = item_info.get("item_id")
    brand = item_info.get("item_brand", "N/A")
    price = float(item_info.get("price", 0.0))
    article = f"goods_{item_id}"

    # 1. Название, Артикул (берем из видимых элементов для надежности)
    name_selector = "div.ProductHead__name, h1.ProductHead__name"
    name = container.locator(name_selector).first.inner_text().strip()

    # 2. Описание и характеристики
    description_locator = container.locator(".infoDescription__full")
    description = description_locator.inner_text().strip() if description_locator.count() > 0 else ""

    characteristics = {}
    if container.locator("ul.infoFeatures li.specTitle:has-text('Характеристики')").count() > 0:
        char_elements = container.locator("ul.infoFeatures li:not(.specTitle)").all()
        for li in char_elements:
            text = li.inner_text().strip()
            parts = re.split(r'\s+[—:]\s+', text, maxsplit=1)
            if len(parts) == 2:
                characteristics[parts[0].strip()] = parts[1].strip()

    # 3. Остатки
    stocks = {}
    stock_rows = page.locator("tr.AvailabilityItem").all()
    for row in stock_rows:
        store_name_locator = row.locator(".AvailabilityLabel")
        if not store_name_locator.count(): continue
        store_name = store_name_locator.inner_text().strip()
        amount_locator = row.locator(".AvailabilityBox--green")
        amount = amount_locator.inner_text().strip() if amount_locator.count() > 0 else "0"
        stocks[store_name] = amount

    # ====================================================================
    # ИЗМЕНЕНИЕ №2: Уникализация ссылок на изображения.
    # ====================================================================
    image_urls = set()  # Используем set для автоматического удаления дублей
    image_locators = container.locator(".ProductPhotoThumb__link").all()
    if image_locators:
        for thumb in image_locators:
            href = thumb.get_attribute('href')
            # Видео-ссылки на youtube тоже отфильтровываем, берем только картинки
            if href and href.startswith('https://s3.ibta.ru'):
                image_urls.add(href)
    else:
        main_image_locator = container.locator(".itemInfoPhotos__link")
        if main_image_locator.count() > 0:
            href = main_image_locator.get_attribute('href')
            if href and href.startswith('https://s3.ibta.ru'):
                image_urls.add(href)

    # 4. Проверка статуса
    order_block_selector = container.locator("div.order")
    red_status_locator = order_block_selector.locator(".ProductState--red")
    if red_status_locator.count() > 0:
        status_text = red_status_locator.first.inner_text().strip()
        if "Недоступен" in status_text or "Есть только в другом сочетании" in status_text:
            raise ValueError(f"Товар недоступен: {status_text}")
        if "Выведен" in status_text:
            raise ValueError("Товар выведен из ассортимента")

    return {
        "name": name, "price": price, "brand": brand, "stocks": stocks,
        "description": description, "characteristics": characteristics,
        "image_urls": list(image_urls),  # Преобразуем set обратно в list для JSON
        "product_url": page.url,
        "article_from_page": article
    }


# --- ГЛАВНАЯ ФУНКЦИЯ (с обновленной логикой) ---
def main():
    start_time = datetime.datetime.now()
    print(f"🚀 Старт скрипта: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # ИЗМЕНЕНИЕ: Используем новую функцию для чтения ссылок
    urls_to_parse = read_simple_urls(INPUT_URL_FILE)
    all_data = load_existing_data(OUTPUT_JSON_FILE)

    # ИЗМЕНЕНИЕ: Немного другая логика извлечения артикула для проверки
    def get_article_from_url(url: str) -> str | None:
        """Извлекает ID товара из URL и формирует артикул 'goods_ID'."""
        match = re.search(r'/goods/(\d+)', url)
        if match:
            return f"goods_{match.group(1)}"
        return None

    urls_to_process = [
        url for url in urls_to_parse
        if (article := get_article_from_url(url)) and article not in all_data
    ]

    if not urls_to_process:
        print("Все товары из списка уже обработаны. Завершение работы.")
        return

    print(f"К обработке {len(urls_to_process)} новых ссылок.")
    newly_added_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")
        context.set_default_timeout(TIMEOUT)
        page = context.new_page()

        if not perform_login(page):
            browser.close()
            return

        for url in tqdm(urls_to_process, desc="Сбор данных о товарах"):
            product_data = None
            article_id_from_url = get_article_from_url(url)
            if not article_id_from_url:
                log_failed_url(url, "Некорректный URL, не удалось извлечь ID", OUTPUT_FAILED_FILE)
                continue

            for attempt in range(MAX_RETRIES):
                try:
                    print(f"\n  [Попытка {attempt + 1}/{MAX_RETRIES}] Обрабатываю {url}")
                    page.goto(url, wait_until="domcontentloaded")
                    page.evaluate(
                        "() => { const chat = document.querySelector('.online-chat-root-TalkMe'); if (chat) chat.remove(); }")
                    product_data = parse_product_page(page)
                    if product_data:
                        print(f"  [Попытка {attempt + 1}] Успешно!")
                        break
                except Exception as e:
                    print(f"  [Попытка {attempt + 1}] ОШИБКА: {e}")
                    debug_article_id_with_attempt = f"{article_id_from_url}_attempt_{attempt + 1}"
                    save_debug_info(page, debug_article_id_with_attempt)
                    if attempt < MAX_RETRIES - 1:
                        print(f"  -> Пауза перед следующей попыткой...")
                        time.sleep(5)

            if product_data:
                all_data[article_id_from_url] = product_data
                newly_added_count += 1
                save_json_data(all_data, OUTPUT_JSON_FILE)
            else:
                print(f"!!! НЕ УДАЛОСЬ обработать {url} после {MAX_RETRIES} попыток.")
                if not any(url in line for line in
                           (open(OUTPUT_FAILED_FILE).readlines() if os.path.exists(OUTPUT_FAILED_FILE) else [])):
                    log_failed_url(url, "Не удалось загрузить или спарсить после всех попыток", OUTPUT_FAILED_FILE)

            time.sleep(random.uniform(*PAUSE_BETWEEN_REQUESTS))

        browser.close()

    end_time = datetime.datetime.now()
    print("-" * 50)
    print(f"🎉 Скрипт завершен: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🕒 Время выполнения: {end_time - start_time}")
    print(f"👍 Добавлено новых товаров: {newly_added_count}")
    print(f"💾 Всего товаров в базе: {len(all_data)}")
    print(f"💾 Результат сохранен в: {os.path.abspath(OUTPUT_JSON_FILE)}")
    print(f"❌ Проблемные ссылки записаны в: {os.path.abspath(OUTPUT_FAILED_FILE)}")
    print(f"🔍 Файлы для отладки сохранены в: {os.path.abspath(DEBUG_DIR)}")
    print("-" * 50)


if __name__ == '__main__':
    main()
