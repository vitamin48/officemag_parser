"""Скрипт на основе playwright считывает каталоги www.officemag.ru из файла input/catalogs.txt и собирает ссылки со всех
имеющихся страниц в файл out/officemag_articles.txt"""

import time
import datetime
from playwright.sync_api import sync_playwright
import traceback
from bs4 import BeautifulSoup
from tqdm import tqdm

url_test = 'https://www.officemag.ru/catalog/1523/index.php?SORT=SORT&COUNT=60'


def read_catalogs_from_txt():
    """Считывает и возвращает список каталогов из файла"""
    with open('input/catalogs.txt', 'r', encoding='utf-8') as file:
        catalogs = [f'{line}'.rstrip() for line in file]
    return catalogs


def write_catalogs_to_txt(list_to_txt):
    with open("result\\art_links.txt", "a", encoding="utf-8") as file:
        for item in list_to_txt:
            file.write(f"{item}\n")


def get_soup_by_html(path_to_html):
    # Открытие и чтение содержимого файла
    with open(path_to_html, "r", encoding='utf-8') as file:
        file_content = file.read()
    soup = BeautifulSoup(file_content, "html.parser")
    return soup


def get_arts_links_by_soup(soup):
    catalog_arts = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/catalog/goods/") and href.count('/') == 4:
            full_link = f"https://www.officemag.ru{href}"
            catalog_arts.append(full_link)
    return set(catalog_arts)


class OfficeMag:
    playwright = None
    browser = None
    page = None
    context = None

    def __init__(self, playwright):
        self.catalogs = read_catalogs_from_txt()
        self.set_playwright_config(playwright=playwright)

    def set_playwright_config(self, playwright):
        js = """
        Object.defineProperties(navigator, {webdriver:{get:()=>undefined}});
        """
        self.playwright = playwright
        self.browser = playwright.chromium.launch(headless=False, args=['--blink-settings=imagesEnabled=false'])
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.add_init_script(js)

    def save_page_as_html(self, url, file_name):
        self.page.goto(url)
        content = self.page.content()  # Получаем HTML содержимое страницы
        with open(file_name, 'w', encoding='utf-8') as f:
            f.write(content)
        self.browser.close()

    def set_city(self):
        self.page.goto("https://www.officemag.ru/auth/")
        self.page.locator("#fancybox-close").click()
        self.page.get_by_label("Электронная почта или логин").click()
        self.page.get_by_label("Электронная почта или логин").fill("forvk180420@gmail.com")
        self.page.get_by_label("Пароль").click()
        self.page.get_by_label("Пароль").fill("forvk180420")
        self.page.get_by_role("button", name="Войти").click()

    def get_arts_from_catalogs(self):
        for catalog in tqdm(self.catalogs):
            page = 1
            while True:
                catalog_url = f'{catalog}index.php?SORT=SORT&COUNT=60&PAGEN_1={page}'
                print(f'Работаю с каталогом: {catalog_url}')
                self.page.goto(catalog_url)
                if self.page.locator(f"text=Товары не найдены").count() > 0:
                    print(f'На странице {page} Товары не найдены')
                    time.sleep(5)
                    break
                else:
                    soup = BeautifulSoup(self.page.content(), 'lxml')
                    catalog_arts = get_arts_links_by_soup(soup)
                    write_catalogs_to_txt(catalog_arts)
                    time.sleep(5)
                    page += 1

    def start(self):
        # self.save_page_as_html(url_test, 'result\\example_catalog.html')
        self.set_city()
        self.get_arts_from_catalogs()
        print()


def main():
    t1 = datetime.datetime.now()
    print(f'Start: {t1}')
    try:
        with sync_playwright() as playwright:
            OfficeMag(playwright=playwright).start()
        print(f'Успешно')
    except Exception as exp:
        print(exp)
        print(traceback.format_exc())
        # send_logs_to_telegram(message=f'Произошла ошибка!\n\n\n{exp}')
    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')
    # send_logs_to_telegram(message=f'Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
    # soup = get_soup_by_html(path_to_html='result\\example_catalog.html')
    # arts_links = get_arts_links(soup)
    print()
