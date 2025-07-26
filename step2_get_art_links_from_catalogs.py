"""
Шаг 2. Сбор ссылок и данных о товарах с авторизацией и фильтрацией.
"""
import os
import time
import datetime
import json
import random
from playwright.sync_api import sync_playwright, TimeoutError
from tqdm import tqdm

# --- НАСТРОЙКИ СКРИПТА ---
# Пути к файлам
INPUT_CATALOGS_FILE = os.path.join("in", "catalogs.txt")
INPUT_BAD_BRANDS_FILE = os.path.join("in", "bad_brand.txt")
OUTPUT_GOOD_FILE = os.path.join("out", "links_from_catalogs.csv")
OUTPUT_BAD_FILE = os.path.join("out", "links_from_catalogs_bad_brand.csv")

# Данные для авторизации
LOGIN_URL = "https://www.officemag.ru/auth/"
USER_LOGIN = "forvk180420@gmail.com"
USER_PASSWORD = "forvk180420"

# Общие константы
BASE_URL = "https://www.officemag.ru"
CSV_HEADERS = ['Артикул', 'Бренд', 'Название', 'Цена', 'Ссылка']
CSV_SEPARATOR = ';'

# Настройки Playwright
HEADLESS_MODE = False
TIMEOUT = 45000
PAUSE_BETWEEN_REQUESTS = (1, 5)


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

# ИЗМЕНЕНИЕ: Новая функция для чтения в список (сохраняет порядок)
def read_file_lines_to_list(filepath: str) -> list[str]:
    """Читает строки из файла в список, сохраняя исходный порядок."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            # Считываем все непустые строки
            lines = [line.strip() for line in file if line.strip()]
            # Убираем дубликаты, сохраняя порядок (трюк с dict.fromkeys)
            return list(dict.fromkeys(lines))
    except FileNotFoundError:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл не найден: {filepath}")
        return []


# ИЗМЕНЕНИЕ: Старую функцию переименовали для ясности
def read_file_lines_to_set(filepath: str) -> set[str]:
    """Читает строки из файла в множество (для быстрой проверки), приводя к нижнему регистру."""
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return {line.strip().lower() for line in file if line.strip()}
    except FileNotFoundError:
        print(f"ПРЕДУПРЕЖДЕНИЕ: Файл не найден: {filepath}")
        return set()


def load_processed_articles_from_csv(*filepaths: str) -> set[str]:
    """Загружает артикулы из нескольких CSV-файлов, чтобы избежать дублей."""
    processed_articles = set()
    print("Загружаю ранее собранные артикулы...")
    for filepath in filepaths:
        if not os.path.exists(filepath):
            continue
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            next(f, None)
            for line in f:
                try:
                    article = line.strip().split(CSV_SEPARATOR)[0]
                    if article:
                        processed_articles.add(article)
                except IndexError:
                    continue
    print(f"Загружено {len(processed_articles)} уникальных артикулов.")
    return processed_articles


def append_data_to_csv(data: list[tuple], filepath: str):
    """Дозаписывает новые данные о товарах в CSV-файл."""
    if not data:
        return
    output_dir = os.path.dirname(filepath)
    os.makedirs(output_dir, exist_ok=True)
    file_exists = os.path.exists(filepath)
    with open(filepath, "a", encoding="utf-8-sig", newline='') as file:
        if not file_exists:
            file.write(CSV_SEPARATOR.join(CSV_HEADERS) + '\n')
        for item in data:
            row = CSV_SEPARATOR.join(map(str, item))
            file.write(row + '\n')
    print(f"Добавлено {len(data)} новых записей в {filepath}")


# --- ЛОГИКА PLAYWRIGHT ---
# (функции perform_login и get_articles_data_from_page остаются без изменений)
def perform_login(page):
    """Выполняет авторизацию на сайте."""
    print("Выполняю авторизацию...")
    try:
        page.goto(LOGIN_URL)
        page.wait_for_load_state('domcontentloaded')
        time.sleep(2)
        print('press Escape')
        page.keyboard.press("Escape")
        time.sleep(2)

        page.get_by_label("Электронная почта или логин").fill(USER_LOGIN)
        page.get_by_label("Пароль").fill(USER_PASSWORD)
        page.get_by_role("button", name="Войти").click()

        page.wait_for_selector("span.User__trigger:has-text('Кабинет')", timeout=15000)
        print("Авторизация прошла успешно.")
        return True
    except Exception as e:
        print(f"ОШИБКА во время авторизации: {e}")
        return False


def get_articles_data_from_page(page) -> list[tuple]:
    """Собирает данные (артикул, бренд, название, цена, ссылка) с текущей страницы."""
    card_selector = "li.listItem.js-productListItem"

    try:
        page.wait_for_selector(card_selector, timeout=15000)
    except TimeoutError:
        return []

    cards = page.locator(card_selector).all()
    articles_data = []

    for card in cards:
        try:
            ga_object_str = card.get_attribute("data-ga-object")
            ga_data = json.loads(ga_object_str)
            item_info = ga_data["items"][0]

            item_id = item_info.get("item_id")
            item_brand = item_info.get("item_brand", "N/A")
            item_price_str = str(item_info.get("price", "0.0")).replace(',', '.')

            link_locator = card.locator(".name a")
            item_name = link_locator.inner_text().strip().replace(CSV_SEPARATOR, ',')
            href = link_locator.get_attribute("href")

            article_id = f"goods_{item_id}"
            full_link = f"{BASE_URL}{href}"
            price = float(item_price_str)

            articles_data.append((article_id, item_brand, item_name, price, full_link))
        except (Exception,):
            continue

    return articles_data


# --- ГЛАВНАЯ ФУНКЦИЯ ---

def main():
    start_time = datetime.datetime.now()
    print(f"🚀 Старт скрипта: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # ИЗМЕНЕНИЕ: Используем разные функции для каталогов (list) и брендов (set)
    catalogs = read_file_lines_to_list(INPUT_CATALOGS_FILE)
    bad_brands = read_file_lines_to_set(INPUT_BAD_BRANDS_FILE)
    processed_articles = load_processed_articles_from_csv(OUTPUT_GOOD_FILE, OUTPUT_BAD_FILE)

    if not catalogs:
        return

    total_new_good = 0
    total_new_bad = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS_MODE)
        context = browser.new_context()
        context.set_default_timeout(TIMEOUT)
        page = context.new_page()

        if not perform_login(page):
            browser.close()
            return

        for catalog_url in tqdm(catalogs, desc="Обработка каталогов"):
            page_num = 1
            print(f"\nНачинаю обход каталога: {catalog_url}")

            while True:
                url = f"{catalog_url}index.php?SORT=SORT&COUNT=60&PAGEN_1={page_num}"
                print(f"  - Загружаю страницу {page_num}...")

                try:
                    page.goto(url, wait_until="domcontentloaded")
                    page.keyboard.press("Escape")

                    if page.locator("text=Товары не найдены").count() > 0:
                        print("  -> Достигнут конец каталога.")
                        break

                    found_data = get_articles_data_from_page(page)

                    if not found_data:
                        print("  -> Данные не найдены, предполагаем конец каталога.")
                        break

                    newly_found_good, newly_found_bad = [], []
                    for item_data in found_data:
                        article_id = item_data[0]
                        if article_id not in processed_articles:
                            processed_articles.add(article_id)
                            brand_normalized = item_data[1].strip().lower()

                            if brand_normalized in bad_brands:
                                newly_found_bad.append(item_data)
                            else:
                                newly_found_good.append(item_data)

                    append_data_to_csv(newly_found_good, OUTPUT_GOOD_FILE)
                    append_data_to_csv(newly_found_bad, OUTPUT_BAD_FILE)
                    total_new_good += len(newly_found_good)
                    total_new_bad += len(newly_found_bad)

                    page_num += 1
                    time.sleep(random.uniform(*PAUSE_BETWEEN_REQUESTS))

                except Exception as e:
                    print(f"  -> КРИТИЧЕСКАЯ ОШИБКА: {e}. Прерываю обход каталога.")
                    break
        browser.close()

    end_time = datetime.datetime.now()
    print("-" * 50)
    print(f"🎉 Скрипт завершен: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🕒 Время выполнения: {end_time - start_time}")
    print(f"👍 Добавлено новых 'хороших' товаров: {total_new_good}")
    print(f"👎 Добавлено новых 'нежелательных' товаров: {total_new_bad}")
    print(f"💾 Результаты сохранены в папке: {os.path.abspath('out')}")
    print("-" * 50)


if __name__ == '__main__':
    main()
