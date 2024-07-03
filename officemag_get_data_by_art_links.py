"""
Скрипт на основе playwright считывает ссылки на товары Офисмаг из файла result/art_links.txt, переходит по ним,
предварительно авторизовавшись, считывает информацию и остатки каждого товара, без учета недружественных брендов,
записывает результаты в файл JSON.

Помимо результирующего файла JSON, формируются дополнительные файлы:
articles_with_bad_req.txt - для ссылок, которые не удалось загрузить, либо другая ошибка с указанием этой ошибки
"""

import requests
import datetime
import time
import re
from tqdm import tqdm
from pathlib import Path
import json
import traceback
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from officemag_get_arts_by_catalogs import get_soup_by_html

LOGIN = 'ropad99662@htoal.com'
PASS = 'kKNkK4ZL$Ci6/ct'


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def read_art_links_from_txt():
    """Считывает и возвращает список ссылок на товары из файла"""
    with open('result/art_links.txt', 'r', encoding='utf-8') as file:
        product_list = [f'{line}'.rstrip() for line in file]
    return product_list


def add_bad_req(art, error=''):
    """Запись в файл ссылок, которые не удалось загрузить, либо другая ошибка с указанием этой ошибки"""
    with open('out/articles_with_bad_req.txt', 'a') as output:
        if error == '':
            output.write(f'{art}\n')
        else:
            output.write(f'{error}\t{art}\n')


def send_logs_to_telegram(message):
    """Отправка уведомления в Telegram"""
    import platform
    import socket
    import os

    platform = platform.system()
    hostname = socket.gethostname()
    user = os.getlogin()

    bot_token = '6456958617:AAF8thQveHkyLLtWtD02Rq1UqYuhfT4LoTc'
    chat_id = '128592002'

    url = f'https://api.telegram.org/bot{bot_token}/sendMessage'
    data = {"chat_id": chat_id, "text": message + f'\n\n{platform}\n{hostname}\n{user}'}
    response = requests.post(url, data=data)
    return response.json()


class OfficeMagParser:
    playwright = None
    browser = None
    page = None
    context = None

    def __init__(self, playwright):
        self.res_list = []
        self.res_dict = {}
        self.product_list = read_art_links_from_txt()
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

    def authorization(self):
        self.page.goto("https://www.officemag.ru/auth/")
        self.page.locator("#fancybox-close").click()
        self.page.get_by_label("Электронная почта или логин").click()
        self.page.get_by_label("Электронная почта или логин").fill(LOGIN)
        self.page.get_by_label("Пароль").click()
        self.page.get_by_label("Пароль").fill(PASS)
        self.page.get_by_role("button", name="Войти").click()

    def get_data_by_page(self, product):
        soup = BeautifulSoup(self.page.content(), 'lxml')
        product_name = self.page.locator('div.ProductHead__name').text_content()
        price = self.page.locator('span.Price__count').text_content()
        brand = self.page.locator('span.ProductBrand__name').text_content()
        description = self.page.locator('div.infoDescription').text_content()
        characteristics = self.page.locator('ul.infoFeatures').text_content()
        # Остатки
        rows = self.page.query_selector_all('.AvailabilityList tbody .AvailabilityItem')
        print()

    def get_data_by_art_links(self):
        """Перебор по ссылкам на товары, получение данных"""
        for product in tqdm(self.product_list):
            retry_count = 1  # Минимальное количество попыток загрузки страницы
            max_retries = 4  # Максимальное количество попыток загрузки страницы
            timeout_for_load_page = 60
            while retry_count < max_retries:
                try:
                    # Переход к странице товара
                    print(f'Загружаю страницу: {product}')
                    response = self.page.goto(product, timeout=30000)
                    self.get_data_by_page(product)
                    print()
                except Exception as exp:
                    # Обработка исключений при загрузке страницы
                    traceback_str = traceback.format_exc()
                    print(f'{bcolors.WARNING}Ошибка при загрузке страницы {product}:\n'
                          f'{exp}\n{traceback_str}{bcolors.ENDC}')
                    # Уменьшаем retry_count на 1
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f'Ждем {timeout_for_load_page} cекунд, затем делаем попытку №{retry_count} '
                              f'из {max_retries - retry_count}.')
                        time.sleep(timeout_for_load_page)
                    else:
                        # Если превышено количество попыток
                        print(f'Превышено количество попыток для товара, в файл добавлено: {product}')
                        add_bad_req(product, error='Превышено_количество_попыток_для_загрузки_страницы_товара')
                        break

    def start(self):
        # self.authorization()
        self.get_data_by_art_links()
        print()


def main():
    t1 = datetime.datetime.now()
    print(f'Start: {t1}')
    try:
        with sync_playwright() as playwright:
            OfficeMagParser(playwright=playwright).start()
        print(f'{bcolors.OKGREEN}Успешно{bcolors.ENDC}')
    except Exception as exp:
        print(exp)
        traceback_str = traceback.format_exc()
        print(traceback_str)
        send_logs_to_telegram(message=f'Произошла ошибка!\n\n\n{exp}\n\n{traceback_str}')
    t2 = datetime.datetime.now()
    print(f'Finish: {t2}, TIME: {t2 - t1}')
    # send_logs_to_telegram(message=f'Finish: {t2}, TIME: {t2 - t1}')


if __name__ == '__main__':
    main()
