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
from officemag_get_arts_by_catalogs_step2 import get_soup_by_html

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
    with open('result/articles_with_bad_req.txt', 'a') as output:
        if error == '':
            output.write(f'{art}\n')
        else:
            output.write(f'{error}\t{art}\n')


def write_json(res_dict):
    with open('result/data.json', 'w', encoding='utf-8') as json_file:
        json.dump(res_dict, json_file, indent=2, ensure_ascii=False)


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

    def restart_browser(self):
        # Закрытие текущего контекста и браузера
        if self.page:
            self.page.close()
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        # Перезапуск браузера и создание нового контекста и страницы
        self.set_playwright_config(self.playwright)

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
        "Код (Артикул)"
        code = product.split('/')[-2]
        "Проверяем, доступен ли товар для заказа"
        product_state_div = soup.find('div', class_='ProductState ProductState--red',
                                      string="Недоступен к заказу")
        if product_state_div:
            add_bad_req(product, error='Недоступен_к_заказу')
            print(f'{bcolors.WARNING}{code} Недоступен к заказу{bcolors.ENDC}')
            return
        "Проверяем, выведен ли товар из ассортимента"
        product_state_div2 = soup.find('div', class_='ProductState ProductState--red',
                                       string=re.compile(r'^Выведен из'))
        if product_state_div2:
            add_bad_req(product, error='Выведен_из_ассортимента')
            print(f'{bcolors.WARNING}{code} Выведен из ассортимента{bcolors.ENDC}')
            return
        # if soup.find('div',class_='ProductState ProductState--red'):
        #     status = soup.find('div',class_='ProductState ProductState--red').text
        #     if status == 'Недоступен к&nbsp;заказу':
        #         add_bad_req(product, error='Недоступен_к_заказу')
        #         print(f'{bcolors.WARNING}Недоступен к заказу{bcolors.ENDC}')
        #         return
        #     elif status == 'Есть только в другом сочетании':
        #         add_bad_req(product, error='Недоступен_к_заказу')
        #         print(f'{bcolors.WARNING}Недоступен к заказу (Есть только в другом сочетании){bcolors.ENDC}')
        #         return
        #     elif status == 'Временно отсутствует на складе':
        #         print(f'Временно отсутствует на складе')
        #     else:
        #         input(f'{bcolors.OKBLUE}Недоступен_к_заказу особый случай{bcolors.ENDC}')
        "характеристики"
        # Находим блок "Подробнее о товаре"
        details_section = soup.find('div', class_='TabsContentSpoiler__content')
        characteristics_dict = {}
        characteristics_text_list = []
        if details_section:
            # Находим все элементы списка характеристик
            characteristics_list = details_section.find('ul', class_='infoFeatures')
            if characteristics_list:
                # Извлекаем текст каждого элемента списка
                for item in characteristics_list.find_all('li'):
                    text = item.get_text(strip=True)
                    # Ищем разделители "-" и ":"
                    if "—" in text:
                        key, value = text.split("—", 1)
                    elif ":" in text:
                        key, value = text.split(":", 1)
                    else:
                        # Если разделителей нет, пропускаем элемент
                        continue
                    characteristics_dict[key.strip()] = value.strip()
                    characteristics_text_list.append(text)
        result_characteristics_text = " ".join(characteristics_text_list)
        "остатки"
        div_stocks = soup.find('div', class_='tabsContent js-tabsContent js-tabsContentMobile')
        rows = div_stocks.find_all('tr', class_='AvailabilityItem')
        data_stocks = {}
        for row in rows:
            store_cell = row.find('td', class_='AvailabilityBox')
            store_name = store_cell.find('span', class_='AvailabilityLabel').text.strip()
            # Извлекаем данные из второй ячейки (наличие товара)
            availability_cell = row.find('td', class_='AvailabilityBox AvailabilityBox--green')
            if availability_cell:
                availability = availability_cell.text.strip()
            else:
                availability = 0
            # Записываем данные в словарь
            data_stocks[store_name] = availability
        "Описание"
        description = (soup.find('div', class_='infoDescription').text.replace('Описание', '')
                       .replace('\n\n', ' ')).replace('\n', ' ').strip()
        # Добавляем к описанию характеристики
        description = description + ' ' + result_characteristics_text
        "Бренд"
        brand = soup.find('span', class_='ProductBrand__name')
        if brand:
            brand = brand.text.strip()
        else:
            brand = 'NoName'
        "Изображения"
        if soup.find('ul', class_='ProductPhotoThumbs'):
            images_soup = (soup.find('ul', class_='ProductPhotoThumbs')
                           .find_all('a', class_='ProductPhotoThumb__link'))
            image_urls = [link['href'] for link in images_soup]
        elif soup.find('span', class_='main js-photoTarget'):
            image_urls = soup.find('a', class_='itemInfoPhotos__link')['href']  # случай, когда изображение одно
        else:
            input(f'{bcolors.OKBLUE}Не найдены изображения особый случай{bcolors.OKBLUE}')
        "Название"
        name = soup.find('div', class_='ProductHead__name').text.strip()
        "Цена"
        # price = soup.find('span', class_='Price__count').text.strip()
        price_soup = soup.find('div', class_='order')
        price = 0
        if price_soup.find('div', class_='Product__price js-itemPropToRemove js-detailCardGoods'):
            price = (price_soup.find('div', class_='Product__price js-itemPropToRemove js-detailCardGoods')
                     .find('span', class_='Price__count').text.strip())
        elif price_soup.find('div', class_='Price Price--best js-priceBigCard js-PriceWrap'):
            price = (price_soup.find('div', class_='Price Price--best js-priceBigCard js-PriceWrap')
                     .find('span', class_='Price__count').text.strip())
        if price == 0:
            input(f'{bcolors.OKBLUE}Цена 0! Особый случай{bcolors.ENDC}')
        # print(price)
        "Формируем результирующий словарь с данными"
        self.res_dict[code] = {'name': name, 'price': price, 'stock': data_stocks, 'description': description,
                               'characteristics': characteristics_dict,
                               'img_urls': image_urls, 'art_url': product, 'code': code, 'brand': brand}
        write_json(res_dict=self.res_dict)
        # print()

    def get_data_by_art_links(self):
        """Перебор по ссылкам на товары, получение данных"""
        for product in tqdm(self.product_list):
            retry_count = 1  # Минимальное количество попыток загрузки страницы
            max_retries = 4  # Максимальное количество попыток загрузки страницы
            timeout_for_load_page = 100
            while retry_count < max_retries:
                try:
                    # Переход к странице товара
                    print(f'Загружаю страницу: {product}')
                    response = self.page.goto(product, timeout=30000)
                    self.get_data_by_page(product)
                    break
                except Exception as exp:
                    # Обработка исключений при загрузке страницы
                    traceback_str = traceback.format_exc()
                    print(f'{bcolors.WARNING}Ошибка при загрузке страницы {product}:\n'
                          f'{exp}\n{traceback_str}{bcolors.ENDC}')
                    # Уменьшаем retry_count на 1
                    retry_count += 1
                    if retry_count < max_retries:
                        print(f'Ждем {timeout_for_load_page} cекунд, затем делаем попытку №{retry_count} '
                              f'из {max_retries - 1}. Также перезапускаем браузер.')
                        time.sleep(5)
                        self.restart_browser()
                        time.sleep(timeout_for_load_page)
                        self.authorization()
                    else:
                        # Если превышено количество попыток
                        print(f'Превышено количество попыток для товара, в файл лога ошибок добавлено: {product}')
                        add_bad_req(product, error='Превышено_количество_попыток_для_загрузки_страницы_товара')
                        send_logs_to_telegram(message=f'Скрипт на паузе. Превышено количество попыток для загрузки '
                                                      f'страницы товара: \n{product}')
                        input('Пауза')
                        break

    def start(self):
        self.authorization()
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

if __name__ == '__main__':
    main()
