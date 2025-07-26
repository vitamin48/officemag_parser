"""
Скрипт считывает все ссылки на все каталоги магазина
со страницы https://www.officemag.ru/catalog/abc/ с помощью Playwright.
На выходе — текстовый файл со списком каталогов.
"""
import os
import time
from playwright.sync_api import sync_playwright, TimeoutError

# --- Константы ---
URL = "https://www.officemag.ru/catalog/abc/"
BASE_URL = "https://www.officemag.ru"
OUTPUT_DIR = "out"
OUTPUT_FILE = "catalogs_officemag.txt"


def get_catalog_links():
    """
    Запускает браузер, переходит на страницу и собирает все ссылки на каталоги.
    """
    print("Запускаем браузер...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # headless=False, чтобы видеть окно браузера
        page = browser.new_page()

        try:
            print(f"Переходим на страницу: {URL}")
            # Переходим на страницу и ждем, пока загрузится основной контент
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)

            # На всякий случай дадим странице секунду на подгрузку динамических элементов
            time.sleep(5)

            print("Ищем ссылки на каталоги...")
            # Находим все ссылки внутри списка с классом 'catalogAlphabetList'
            # Это самый надежный селектор для нашей задачи
            link_locators = page.locator("ul.catalogAlphabetList li a")

            # Считаем количество найденных элементов
            count = link_locators.count()
            if count == 0:
                print("Не найдено ни одной ссылки. Возможно, изменилась структура сайта.")
                return []

            print(f"Найдено ссылок: {count}. Обрабатываем...")

            catalog_links = []
            # Проходим по всем найденным локаторам
            for locator in link_locators.all():
                href = locator.get_attribute("href")
                if href and href.startswith("/catalog/"):
                    full_link = f"{BASE_URL}{href}"
                    catalog_links.append(full_link)

            print("Сбор ссылок завершен.")
            return catalog_links

        except TimeoutError:
            print(f"Ошибка: страница {URL} не загрузилась за 60 секунд.")
            return []
        except Exception as e:
            print(f"Произошла непредвиденная ошибка: {e}")
            return []
        finally:
            print("Закрываем браузер.")
            browser.close()


def save_links(links, directory, filename):
    """
    Сохраняет список ссылок в текстовый файл.
    """
    if not links:
        print("Список ссылок пуст. Файл не будет создан.")
        return

    # Создаем папку 'result', если ее нет
    os.makedirs(directory, exist_ok=True)

    # Полный путь к файлу
    filepath = os.path.join(directory, filename)

    print(f"Сохраняем ссылки в файл: {filepath}")
    with open(filepath, "w", encoding="utf-8") as f:
        for link in links:
            f.write(f"{link}\n")
    print("Файл успешно сохранен.")


if __name__ == '__main__':
    all_links = get_catalog_links()
    save_links(all_links, directory=OUTPUT_DIR, filename=OUTPUT_FILE)