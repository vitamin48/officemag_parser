"""
Шаг 3. Сбор детальной информации о товарах.

Скрипт считывает "хороший" список ссылок из файла /out/url_data.csv.
Выполняет авторизацию, затем последовательно обходит каждую ссылку.

Для каждого товара собирает детальную информацию:
- Название, цена, бренд
- Описание и характеристики
- Остатки по складам и магазинам
- Ссылки на изображения

Успешно собранные данные сохраняются в файл /out/products_data.json.
Ссылки, которые не удалось обработать, записываются в /out/failed_urls.txt с указанием причины.
"""
import os
import time
import datetime
import json
import random
from playwright.sync_api import sync_playwright, TimeoutError, Page
from tqdm import tqdm
import re

# --- НАСТРОЙКИ СКРИПТА ---
# Пути к файлам
INPUT_URL_FILE = os.path.join("out", "url_data.csv")
OUTPUT_JSON_FILE = os.path.join("out", "products_data.json")
OUTPUT_FAILED_FILE = os.path.join("out", "failed_urls.txt")

# Данные для авторизации
LOGIN_URL = "https://www.officemag.ru/auth/"
USER_LOGIN = "forvk180420@gmail.com"
USER_PASSWORD = "forvk180420"

# Общие константы
BASE_URL = "https://www.officemag.ru"
CSV_SEPARATOR = ';'

# Настройки Playwright
HEADLESS_MODE = False
TIMEOUT = 30000  # 30 секунд на операцию
MAX_RETRIES = 3  # Количество попыток загрузить одну страницу
PAUSE_BETWEEN_REQUESTS = (2, 5)


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def load_urls_to_parse(filepath: str) -> list[str]:
    """Загружает ссылки на товары из CSV-файла (5-й столбец)."""
    if not os.path.exists(filepath):
        print(f"ОШИБКА: Входной файл не найден: {filepath}")
        return []

    urls = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        next(f, None)  # Пропускаем заголовок
        for line in f:
            try:
                # Ссылка находится в последнем столбце
                url = line.strip().split(CSV_SEPARATOR)[-1]
                if url.startswith('http'):
                    urls.append(url)
            except IndexError:
                continue
    print(f"Загружено {len(urls)} ссылок для обработки.")
    return urls


def load_existing_data(filepath: str) -> dict:
    """Загружает ранее собранные данные из JSON-файла."""
    if not os.path.exists(filepath):
        return {}

    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            print(f"Загружено {len(data)} уже собранных товаров из JSON.")
            return data
        except json.JSONDecodeError:
            print(f"ПРЕДУПРЕЖДЕНИЕ: JSON-файл {filepath} поврежден. Начинаем с нуля.")
            return {}


def save_json_data(data: dict, filepath: str):
    """Сохраняет/перезаписывает словарь с данными в JSON-файл."""
    output_dir = os.path.dirname(filepath)
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def log_failed_url(url: str, reason: str, filepath: str):
    """Записывает проблемную ссылку и причину в лог-файл."""
    output_dir = os.path.dirname(filepath)
    os.makedirs(output_dir, exist_ok=True)
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} | {reason} | {url}\n")


# --- ЛОГИКА PLAYWRIGHT ---

def perform_login(page: Page):
    # (Эта функция остается такой же, как в шаге 2)
    print("Выполняю авторизацию...")
    try:
        page.goto(LOGIN_URL)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(3)
        page.keyboard.press("Escape")
        time.sleep(3)

        page.get_by_label("Электронная почта или логин").fill(USER_LOGIN)
        page.get_by_label("Пароль").fill(USER_PASSWORD)
        page.get_by_role("button", name="Войти").click()

        page.wait_for_selector("span.User__trigger:has-text('Кабинет')", timeout=15000)
        print("Авторизация прошла успешно.")
        return True
    except Exception as e:
        print(f"ОШИБКА во время авторизации: {e}")
        return False


def parse_product_page(page: Page) -> dict | None:
    """Извлекает всю информацию с открытой страницы товара (обновленная, более надежная версия)."""
    try:
        # ====================================================================
        # ГЛАВНОЕ ИЗМЕНЕНИЕ: Сначала ждем ключевой элемент, потом работаем.
        # Это гарантирует, что динамический контент успел подгрузиться.
        # ====================================================================
        main_content_selector = "h1.ProductHead__name"
        print(f"  - Жду появления основного контента ({main_content_selector})...")
        page.wait_for_selector(main_content_selector, timeout=20000)  # Даем 20 секунд именно на это
        print("  - Контент загружен, начинаю парсинг.")

        # 1. Основные данные (название, бренд, артикул)
        name = page.locator(main_content_selector).inner_text().strip()

        # Используем альтернативный, более надежный способ получить JSON
        ga_data_locator = page.locator(".itemInfoDetails[data-ga-object]")
        if ga_data_locator.count() > 0:
            ga_data_str = ga_data_locator.get_attribute("data-ga-object")
            ga_data = json.loads(ga_data_str)
            item_info = ga_data["items"][0]
            brand = item_info.get("item_brand", "N/A")
            price = float(item_info.get("price", 0.0))
        else:
            # План Б: если JSON нет, пытаемся спарсить со страницы
            brand_locator = page.locator(".ProductBrand__name")
            brand = brand_locator.inner_text().strip() if brand_locator.count() > 0 else "N/A"
            price_locator = page.locator("div[itemprop='price']")
            price_str = price_locator.get_attribute('content') if price_locator.count() > 0 else "0.0"
            price = float(price_str)

        code_text = page.locator(".ProductHead__code").inner_text()
        article = f"goods_{code_text.replace('Код', '').strip()}"

        # 3. Описание и характеристики
        description_locator = page.locator(".infoDescription__full")
        description = description_locator.inner_text().strip() if description_locator.count() > 0 else ""

        characteristics = {}
        if page.locator("ul.infoFeatures li.specTitle:has-text('Характеристики')").count() > 0:
            char_elements = page.locator("ul.infoFeatures li:not(.specTitle)").all()
            for li in char_elements:
                text = li.inner_text().strip()
                parts = re.split(r'\s+[—:]\s+', text, maxsplit=1)
                if len(parts) == 2:
                    characteristics[parts[0].strip()] = parts[1].strip()

        # 4. Остатки
        stocks = {}
        stock_rows = page.locator(".AvailabilityItem").all()
        for row in stock_rows:
            store_name_locator = row.locator(".AvailabilityLabel")
            if not store_name_locator.count(): continue
            store_name = store_name_locator.inner_text().strip()
            amount_locator = row.locator(".AvailabilityBox--green")
            amount = amount_locator.inner_text().strip() if amount_locator.count() > 0 else "0"
            stocks[store_name] = amount

        # 5. Изображения
        images = []
        image_locators = page.locator(".ProductPhotoThumb__link").all()
        if image_locators:
            images.extend(thumb.get_attribute('href') for thumb in image_locators if thumb.get_attribute('href'))
        else:
            main_image_locator = page.locator(".itemInfoPhotos__link")
            if main_image_locator.count() > 0:
                href = main_image_locator.get_attribute('href')
                if href: images.append(href)

        # 6. Проверка статуса
        red_status_locator = page.locator(".ProductState--red")
        if red_status_locator.count() > 0:
            status_text = red_status_locator.inner_text().strip()
            if "Недоступен" in status_text: raise ValueError("Товар недоступен к заказу")
            if "Выведен" in status_text: raise ValueError("Товар выведен из ассортимента")

        return {
            "name": name, "price": price, "brand": brand, "stocks": stocks,
            "description": description, "characteristics": characteristics,
            "image_urls": images, "product_url": page.url
        }

    except ValueError as ve:
        log_failed_url(page.url, str(ve), OUTPUT_FAILED_FILE)
        print(f"ПРЕДУПРЕЖДЕНИЕ: {str(ve)} для {page.url}")
        return None
    except Exception as e:
        # Теперь эта ошибка будет более информативной
        print(f"ОШИБКА парсинга страницы {page.url}: {e}")
        log_failed_url(page.url, f"Ошибка парсинга: {e}", OUTPUT_FAILED_FILE)
        return None


# --- ГЛАВНАЯ ФУНКЦИЯ ---

def main():
    start_time = datetime.datetime.now()
    print(f"🚀 Старт скрипта: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    urls_to_parse = load_urls_to_parse(INPUT_URL_FILE)
    all_data = load_existing_data(OUTPUT_JSON_FILE)

    urls_to_process = [url for url in urls_to_parse if f"goods_{url.split('/')[-2]}" not in all_data]

    if not urls_to_process:
        print("Все товары уже обработаны. Завершение работы.")
        return

    print(f"К обработке {len(urls_to_process)} новых ссылок.")

    newly_added_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context()
        context.set_default_timeout(TIMEOUT)
        page = context.new_page()

        if not perform_login(page):
            browser.close()
            return

        for url in tqdm(urls_to_process, desc="Сбор данных о товарах"):
            product_data = None
            for attempt in range(MAX_RETRIES):
                try:
                    # ==========================================================
                    # ИЗМЕНЕНИЕ №1: Используем 'networkidle' для полного ожидания
                    # ==========================================================
                    print('sleep3')
                    time.sleep(3)
                    page.goto(url, wait_until="networkidle")
                    print('sleep5')
                    time.sleep(5)

                    # ==========================================================
                    # ИЗМЕНЕНИЕ №2: Дополнительно ждем главный контейнер
                    # ==========================================================
                    page.wait_for_selector("div.contentWrapper.js-productContentWrap", timeout=TIMEOUT)

                    # Закрываем модальное окно, если оно есть
                    try:
                        page.keyboard.press("Escape")
                    except Exception:
                        pass  # Игнорируем ошибку, если окна нет

                    product_data = parse_product_page(page)
                    if product_data:
                        break
                except TimeoutError:
                    print(f"Попытка {attempt + 1}/{MAX_RETRIES}: Страница {url} не загрузилась полностью. Повтор...")
                    time.sleep(5)
                except Exception as e:
                    print(f"Неизвестная ошибка при загрузке {url}: {e}")
                    break

            if product_data:
                article = f"goods_{url.split('/')[-2]}"
                all_data[article] = product_data
                newly_added_count += 1
                save_json_data(all_data, OUTPUT_JSON_FILE)
            else:
                print(f"Не удалось обработать {url} после {MAX_RETRIES} попыток.")
                if not any(url in line for line in
                           (open(OUTPUT_FAILED_FILE).readlines() if os.path.exists(OUTPUT_FAILED_FILE) else [])):
                    log_failed_url(url, "Не удалось загрузить или спарсить", OUTPUT_FAILED_FILE)

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
    print("-" * 50)


if __name__ == '__main__':
    main()
