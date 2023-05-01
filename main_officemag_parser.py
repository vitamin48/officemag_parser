"""Парсер магазина officemag (https://www.officemag.ru/)"""
import re
from pathlib import Path
import requests
import time
import ast
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm
from datetime import date
import urllib

from urllib.request import urlopen as uReq
import json

from selenium.webdriver import Chrome
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait as wait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver import Keys, ActionChains
from time import sleep


class WriteFile:
    def __init__(self, values):
        self.values = values

    def write_txt_file_catalog_status(self):
        with open('result\\checked_articles.txt', 'a') as output:
            for row in self.values:
                output.write(str(row) + '\n')

    def write_txt_articles_and_names(self):
        with open('result\\articles_with_name_category.txt', 'a') as output:
            for row in self.values:
                output.write(str(row) + '\n')


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


class ActualCatalog:
    def __init__(self, proxy_list):
        self.catalog = 'https://www.officemag.ru/catalog/goods/'
        self.proxy_list = proxy_list

    def get_catalog_status(self, from_number, to_number):
        actual_catalog_list = []
        bad_proxy_list = []
        delta_time = 0
        # cur_i = desc = pr = 'start'
        for i in range(from_number, to_number + 1):
            start = time.time()
            # desc = f'\nДля артикула: {i} используется прокси: {pr}'
            for pr in self.proxy_list:
                if len(self.proxy_list) == len(bad_proxy_list):
                    print(f'Закончились прокси! Последний проверенный артикул: {i - 1}')
                    return actual_catalog_list
                if pr in bad_proxy_list:
                    continue
                else:
                    print(f'Для артикула: {i} используется прокси: {pr}. Прогресс: {i - from_number} из '
                          f'{to_number - from_number} '
                          f'({round((i - from_number + 0.0000001) / (to_number - from_number) * 100, 1)} %)'
                          f' Скорость: {delta_time}')
                    if delta_time > 35:
                        # print(f'{bcolors.OKBLUE}Скорость опустилась до 35 секунд за итерацию!{bcolors.ENDC}')
                        print(f'Скорость опустилась до 35 секунд за итерацию!')
                        # continue
                    act_url = self.catalog + f'{i}'
                    try:
                        r = requests.get(act_url, proxies={'https': f'{pr}'}, timeout=5.5)
                        soup = BeautifulSoup(r.text, 'lxml')
                        iteminfodetails = soup.find('div', class_='itemInfoDetails group')
                        registration = soup.find('div', class_='registrationHintDescription')
                        if registration:
                            # print(f'{bcolors.FAIL}БАН на сайте для прокси: {pr}{bcolors.ENDC}')
                            print(f'БАН на сайте для прокси: {pr}')
                            bad_proxy_list.append(pr)
                            continue
                        if iteminfodetails:
                            actual_catalog_list.append(i)
                        break
                    except Exception as exp:
                        # print(f'{bcolors.WARNING}Нерабочий прокси: {pr}. '
                        #       f'Ошибка: {exp.__class__.__name__}{bcolors.ENDC}')
                        print(f'Нерабочий прокси: {pr}. '
                              f'Ошибка: {exp.__class__.__name__}')
                        bad_proxy_list.append(pr)
            end = time.time()
            delta_time = round((end - start), 2)
        return actual_catalog_list


class ParseDiscontProduct:
    """Парсер раздела УСПЕЙ КУПИТЬ ВЫГОДНО"""

    def __init__(self):
        self.__main_page = 'https://www.officemag.ru/promo/actions/?action_kind=manual&SORT=SORT&COUNT=60&PAGEN_1='
        self.first_page = self.__main_page + '1'

    def get_soup(self, page=1):
        r = uReq(f'{self.__main_page}{page}')  # новый синтаксический анализатор
        soup = BeautifulSoup(r.read(), 'lxml')
        return soup

    def cleanstring(self, incomingstring):
        newstring = incomingstring
        newstring = newstring.replace('&laquo;', '')
        newstring = newstring.replace('&raquo;', '')
        newstring = newstring.replace('/<wbr/>', ',')
        newstring = newstring.replace('&times;', '*')
        return newstring

    def get_current_city(self, soup):
        """Находим выбранный город"""
        city = soup.find('ul', class_='HeaderMenu__list HeaderMenu__list--info'). \
            find('li', class_='HeaderMenu__item HeaderMenu__item--cityDetector '
                              'js-dropdownCity js-getSelectedCity js-notHref'). \
            find('a', class_='HeaderMenu__link CityDetector js-cityDetector').text.strip().split('\n')[0].strip()
        return city

    def get_list_items(self):
        status = True
        page = 1
        df = pd.DataFrame()
        name_list = []
        url_list = []
        src_img_list = []
        price_old_list = []
        price_discont_list = []
        krasnoarmeyskaya_list = []
        sovetskaya_list = []
        while status:
            soup = self.get_soup(page)
            city = self.get_current_city(soup)
            if soup.find('div', class_='itemsNotFound'):
                status = False
            else:
                print(f'page={page}')
                page += 1
            time.sleep(3)
            if city == 'Брянск':
                listitems = soup.findAll('li', class_='js-productListItem')
                for item in listitems:
                    minimum = item.find('div', class_='ProductState ProductState--gray')
                    if minimum:
                        # mn = [x for x in minimum.contents if x == 'a']
                        minimum_batch = item.find('div', class_='ProductState ProductState--gray').contents
                        if len(minimum_batch) == 1:
                            minimum_batch = int(re.findall(r'\d+', minimum_batch[0])[0])
                        elif len(minimum_batch) == 2:
                            minimum_batch = int(re.findall(r'\d+', minimum_batch[1])[0])
                        if item.find('div', class_='Product__specialCondition') or minimum_batch != 1:
                            continue
                        else:
                            url_global = item.find('a', href=True)
                            url = url_global.attrs.get('href')
                            src_img = url_global.contents[0].attrs.get('src')
                            name = url_global.contents[0].attrs.get('alt')
                            name = self.cleanstring(name)
                            price_old = float(
                                item.find('div', class_='Product__priceWrapper').text.strip().split('руб.')[0].
                                replace(',', '.').replace(' ', '').replace(' ', ''))
                            price_discont = float(
                                item.find('div', class_='Product__priceWrapper').text.strip().split('руб.')[1].
                                replace(',', '.').replace(' ', '').replace(' ', ''))
                            availability = item.find('div',
                                                     class_='ProductState ProductState--storeAvailability ProductState--green')
                            shop_list = json.loads(availability.contents[1].attrs['data-content-replace'])
                            krasnoarmeyskaya = sovetskaya = ''
                            if shop_list.get('omr_20C') == 'green':
                                krasnoarmeyskaya = int(
                                    json.loads(availability.contents[1].attrs['data-content-replace']).get(
                                        'omr_20T').replace(
                                        ' шт.', ''))
                            elif shop_list.get('omr_20C') == 'red':
                                krasnoarmeyskaya = 0
                            if shop_list.get('omr_102C') == 'green':
                                sovetskaya = int(
                                    json.loads(availability.contents[1].attrs['data-content-replace']).get(
                                        'omr_102T').replace(
                                        ' шт.', ''))
                            elif shop_list.get('omr_102C') == 'red':
                                sovetskaya = 0
                            if krasnoarmeyskaya == sovetskaya == 0:
                                continue
                            else:
                                name_list.append(name)
                                url_list.append(url)
                                src_img_list.append(src_img)
                                price_old_list.append(price_old)
                                price_discont_list.append(price_discont)
                                krasnoarmeyskaya_list.append(krasnoarmeyskaya)
                                sovetskaya_list.append(sovetskaya)
                            print('next_product')
                    else:
                        print('minimum==NONE (нет наличия)')

            else:
                pass
        df.insert(0, 'Название', name_list)
        df.insert(1, 'Цена без скидки', price_old_list)
        df.insert(2, 'Цена со скидкой', price_discont_list)
        df.insert(3, 'Остаток на Советской', sovetskaya_list)
        df.insert(4, 'Остаток на Красноармейской', krasnoarmeyskaya_list)
        df.insert(5, 'URL', url_list)
        df.insert(6, 'Ссылка на изображение', src_img_list)
        XLS().create_from_one_df(df, 'Товары со скидками', 'res_parse')

        name_list.clear()
        url_list.clear()
        src_img_list.clear()
        price_old_list.clear()
        price_discont_list.clear()
        krasnoarmeyskaya_list.clear()
        sovetskaya_list.clear()


class ParseEachProduct:
    def __init__(self):
        self.save_path = f'{str(Path(__file__).parents[1])}\\officemag_parser'
        self.__main_url = 'https://www.officemag.ru/'

    def get_soup(self, code):
        r = uReq(f'{self.__main_url}{code}')
        if r.code == 200:  # новый синтаксический анализатор
            soup = BeautifulSoup(r.read(), 'lxml')
            return soup
        else:
            print(f'Ошибка: {r.code}:\ncode={code}')

    def check_ban(self):
        """Проверка на бан и возврат текущего города"""
        r = uReq(f'{self.__main_url}')
        if r.code == 200:  # новый синтаксический анализатор
            soup = BeautifulSoup(r.read(), 'lxml')
            registration = soup.find('div', class_='registrationHintDescription')
            city = ParseEachProduct().get_current_city(soup)
            if registration:
                print('БАН')
                return {'status': 'ban'}
            else:
                return {'status': 'OK', 'city': city}
        else:
            print(f'Ошибка при запросе: {r.code}')
            return {'status': 'error'}

    def check_ban_and_proxy(self, baned_proxy):
        """Проверка на бан и прокси возврат текущего города"""
        with open('input\\proxy_file_checked.txt', 'r') as proxy_file:
            proxy_list = proxy_file.readlines()
        for proxy in proxy_list:
            proxy = proxy.split('\n')[0]
            if proxy in baned_proxy:
                continue
            else:
                if proxy == 'WITHOUT_PROXY':
                    proxy = ''
                try:
                    res = requests.get('https://ipinfo.io/json', proxies={'https': proxy}, timeout=3)
                    print(f'{proxy} + \n{res.text}')
                    if res.status_code == 200:
                        r = requests.get(f'{self.__main_url}')
                        if r.status_code == 200:
                            soup = BeautifulSoup(r.text, 'lxml')
                            registration = soup.find('div', class_='registrationHintDescription')
                            city = ParseEachProduct().get_current_city(soup)
                            if registration:
                                print('БАН')
                                return {'status': 'ban', 'proxy': proxy}
                            else:
                                return {'status': 'OK', 'city': city, 'proxy': proxy}
                        else:
                            print(f'Ошибка при запросе: {r.status_code}')
                            return {'status': 'error'}
                except Exception as exp:
                    print(f'{proxy} - Exception: {exp}')

        print('Все прокси недоступны')
        return {'status': 'Все прокси недоступны'}

    def get_current_city(self, soup):
        """Находим выбранный город"""
        try:
            city = soup.find('ul', class_='HeaderMenu__list HeaderMenu__list--info'). \
                find('li', class_='HeaderMenu__item HeaderMenu__item--cityDetector '
                                  'js-dropdownCity js-getSelectedCity js-notHref'). \
                find('a', class_='HeaderMenu__link CityDetector js-cityDetector').text.strip().split('\n')[0].strip()
            return city
        except:
            city = soup.find('a', class_='HeaderMenu__link CityDetector').text.strip()
            return city

    def get_attr_each_product(self, df):
        description_list = []  # описание
        features_colour_list = []  # цвет
        features_package_weight_list = []  # вес в упаковке
        features_package_length_list = []  # Длина упаковки
        features_packing_width_list = []  # ширина в упаковке
        features_packing_height_list = []  # Высота упаковки

        features_manufacturer_list = []  # Производитель
        url_main_img_add_list = []  # основное фото товара
        url_img_add_list = []  # дополнительные ссылки на товар из карточки
        video_lst = []  # видео товара
        price_discont_list = []  # цена с учетом скидки
        krasnoarmeyskaya_list = []
        sovetskaya_list = []

        url_list = df['URL'].tolist()
        fr = 76
        to = 100
        for u in range(len(url_list)):
            # for u in range(len(url_list)):
            code = url_list[u][1:]
            print(f'code ======{code}')
            soup = self.get_soup(code=code)
            if soup.find('span', class_='Price Price--best'):
                price = float((soup.find('span', class_='Price Price--best').find('span', class_='Price__count').text +
                               '.' + soup.find('span', class_='Price Price--best').
                               find('span', class_='Price__penny').text).replace(' ', '').replace(u'\xa0', ''))
                price_discont_list.append(price)
            else:
                price = float(soup.find('span', class_='Price__count').text + '.'
                              + soup.find('span', class_='Price__penny').text)
                price_discont_list.append(price)
                print(f'Товар: {code} без зачеркнутой цены')

            check_count_url_img = soup.find('ul', class_='ProductPhotoThumbs')
            if check_count_url_img:
                url = []
                main_url = [soup.find('ul', class_='ProductPhotoThumbs').find('li', class_='ProductPhotoThumb active').
                            find('a', href=True)['href']]
                surl = soup.find('ul', class_='ProductPhotoThumbs').findAll('li', class_='ProductPhotoThumb')
                video_present = False
                for su in surl:
                    url_img = su.find('a', href=True)['href']
                    if 'https://img.youtube.com/' in url_img:
                        youtube_url = soup.find('input', class_='js-productVideoID').attrs.get('value')
                        video_lst.append(youtube_url)
                        video_present = True
                        print()
                    else:
                        url.append(url_img)
                if video_present is False:
                    video_lst.append('-')
                    video_present = True
                url_str = ' '.join(url[1:17])
                url_img_add_list.append(url_str)
                main_url_str = ''.join(main_url)
                url_main_img_add_list.append(main_url_str)
            elif check_count_url_img is None:
                url_from_main_parse = df['Ссылка на изображение'].to_list()[u]
                url_img_add_list.append(url_from_main_parse)
            tabscontent = soup.find('div',
                                    class_='tabsContent js-tabsContent js-tabsContentMobile')  # общая таблица внизу
            description = tabscontent.find('div', class_='infoDescription').text.replace('\nОписание\n\n', '')
            description_list.append(description)
            shops = tabscontent.find('div', class_='tabsContent__item pickup'). \
                find('table', class_='AvailabilityList AvailabilityList--dotted'). \
                findAll('td', 'AvailabilityBox')
            krasnoarmeyskaya = shops[1].text
            if 'заказ' in krasnoarmeyskaya:
                krasnoarmeyskaya = 0
            elif 'Поступит' in krasnoarmeyskaya:
                krasnoarmeyskaya = 0
            else:
                krasnoarmeyskaya = int(krasnoarmeyskaya.replace('шт', '').replace(' ', '').replace('.', ''))
            sovetskaya = shops[3].text
            if 'заказ' in sovetskaya:
                sovetskaya = 0
            elif 'Поступит' in sovetskaya:
                sovetskaya = 0
            else:
                sovetskaya = int(sovetskaya.replace('шт', '').replace(' ', '').replace('.', ''))
            krasnoarmeyskaya_list.append(krasnoarmeyskaya)
            sovetskaya_list.append(sovetskaya)
            print()

            features = tabscontent.find('ul', class_='infoFeatures')  # общий раздел характеристики
            li_set = features.find_all('li')
            l = len(li_set)
            find_colour = False
            for i in li_set:
                print(i.text)
                if 'Цвет — ' in i.text:
                    features_colour_list.append(i.text.replace('Цвет — ', '')[:-1])
                    find_colour = True
                # if any('Цвет — ' in s for s in li_set):
                #     if 'Цвет — ' in i.text:
                #         features_colour_list.append(i.text.replace('Цвет — ', '')[:-1])
                # else:
                #     features_colour_list.append('-')
                if 'Вес с упаковкой' in i.text:
                    weight = i.text.replace('Вес с упаковкой', '').replace('\n', '').replace(' ', '').replace('—', '')
                    if 'кг' in weight:
                        weight = int((float(weight.replace('кг', '').replace(',', '.')) * 1000))
                        features_package_weight_list.append(weight)
                    else:
                        weight = int(weight.replace('г', ''))
                        features_package_weight_list.append(weight)
                elif 'Размер в упаковке' in i.text:
                    string = i.text.replace('Размер в упаковке', '').replace('\n', '').replace('—', '').replace(' ', '')
                    if 'см' in string:
                        string = string.replace('см', '')
                        length = int(float(string.split('x')[0]) * 10)
                        width = int(float(string.split('x')[1]) * 10)
                        height = int(float(string.split('x')[2]) * 10)
                        features_package_length_list.append(length)
                        features_packing_width_list.append(width)
                        features_packing_height_list.append(height)
                    else:
                        print(f'Ошибка: в строке \n\n{i.text}\n\nв разделе размер нет см')
                elif 'Производитель — ' in i.text:
                    manufacturer = i.text.replace('Производитель — ', '').replace(' ', '').replace('\n', '')
                    features_manufacturer_list.append(manufacturer)
                print()
            if not find_colour:
                features_colour_list.append('-')
            time.sleep(2)
            print()

        df_each_product = pd.DataFrame()
        df_each_product.insert(0, 'Code', url_list)
        df_each_product.insert(1, 'Название', df['Название'].to_list())
        df_each_product.insert(2, 'Цена со скидкой', price_discont_list)
        df_each_product.insert(3, 'Актуальный остаток на Советской', sovetskaya_list)
        df_each_product.insert(4, 'Предыдущий остаток на Советской', df['Остаток на Советской'].to_list())
        df_each_product.insert(5, 'Актуальный остаток на Красноармейской', krasnoarmeyskaya_list)
        df_each_product.insert(6, 'Предыдущий остаток на Красноармейской',
                               df['Остаток на Красноармейской'].to_list())
        df_each_product.insert(7, 'Описание', description_list)
        df_each_product.insert(8, 'Цвет', features_colour_list)
        df_each_product.insert(9, 'Вес в упаковке (г)', features_package_weight_list)
        df_each_product.insert(10, 'Ширина в упаковке (мм)', features_packing_width_list)
        df_each_product.insert(11, 'Высота упаковки (мм)', features_packing_height_list)
        df_each_product.insert(12, 'Длина упаковки (мм)', features_package_length_list)
        df_each_product.insert(13, 'Производитель', features_manufacturer_list)
        df_each_product.insert(14, 'Ссылка на главное фото товара', url_main_img_add_list)
        df_each_product.insert(15, 'Ссылки на фото товара', url_img_add_list)
        # df_each_product.insert(16, 'Ссылка на видео товара', video_lst)
        XLS().create_from_one_df(df_each_product, 'Товары', 'res_parse_product')


class XLS:
    def __init__(self):
        self.save_path = f'{str(Path(__file__).parents[1])}\\officemag_parser'
        self.path_res_parse = f'{str(Path(__file__).parents[1])}\\officemag_parser\\res_parse.xlsx'

    def create_from_one_df(self, df, sheet, file_name):
        """Создание файла excel из 1-го DataFrame"""
        path = f'{self.save_path}\\result\\{file_name}.xlsx'
        writer = pd.ExcelWriter(path, engine_kwargs={'options': {'strings_to_urls': False}})
        df.to_excel(writer, sheet_name=sheet, index=False, na_rep='NaN', engine='openpyxl')
        # Auto-adjust columns' width
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            col_idx = df.columns.get_loc(column)
            writer.sheets[f'{sheet}'].set_column(col_idx, col_idx, column_width)
        writer.sheets[sheet].set_column(1, 1, 30)
        writer.sheets[sheet].set_column(8, 8, 30)
        writer.sheets[sheet].set_column(9, 9, 30)
        writer.sheets[sheet].set_column(15, 15, 30)
        writer.sheets[sheet].set_column(16, 16, 30)
        # writer.sheets[sheet].set_column(17, 17, 30)
        writer.close()
        return path

    def read_xls_to_pd(self, path_to_file=f'{str(Path(__file__).parents[1])}\\officemag_parser\\res_parse.xlsx',
                       sheet_name='Товары со скидками'):
        discont_product_df = pd.read_excel(path_to_file, sheet_name=sheet_name)
        return discont_product_df


class SeleniumParse:
    def __init__(self, articles_with_catalog, arts):
        self.save_path = f'{str(Path(__file__).parents[1])}\\officemag_parser'
        self.__main_url = 'https://www.officemag.ru/'
        self.options = Options()
        self.options.add_argument("--start-maximized")
        self.service = Service('chromedriver.exe')
        # self.browser = webdriver.Chrome(service=self.service, options=self.options)
        self.soup_list = []
        self.articles_with_catalog = articles_with_catalog
        self.arts = arts
        self.baned_proxy = []
        self.bad_brand_list = ['Lavazza', 'BRAUBERG', 'DURACELL', 'SYNERGETIC', 'SONNEN', 'JACOBS']
        self.remove_from_description = ['в нашем интернет-магазине', 'у нас на сайте']
        self.update_arts = []
        self.df_each_product = pd.DataFrame()

        self.result_arts = []
        self.product_name = []  # Название товара
        self.brand = []
        self.description_list = []  # описание
        self.features_colour_list = []  # цвет
        self.features_package_weight_list = []  # вес в упаковке
        self.features_package_length_list = []  # Длина упаковки
        self.features_packing_width_list = []  # ширина в упаковке
        self.features_packing_height_list = []  # Высота упаковки
        self.features_manufacturer_list = []  # Производитель
        self.url_main_img_add_list = []  # основное фото товара
        self.url_img_add_list = []  # дополнительные ссылки на товар из карточки
        self.video_lst = []  # видео товара
        self.price_discount_list = []  # цена с учетом скидки
        self.krasnoarmeyskaya_list = []
        self.sovetskaya_list = []

    def set_city_and_get_data(self):
        soup_check = ParseEachProduct().check_ban_and_proxy(baned_proxy=self.baned_proxy)
        if soup_check.get('status') == 'OK':
            self.options.add_argument(f"--proxy-server={soup_check.get('proxy')}")
            self.options.add_argument('--blink-settings=imagesEnabled=false')
            # self.options.add_argument(f"--proxy-server={proxy}")
            browser = webdriver.Chrome(service=self.service, options=self.options)
            browser.get('https://ipinfo.io/json')
            browser.get(self.__main_url)
            # city_btn = self.browser.find_element(By.XPATH, '/html/body/div[2]/div[2]/a[2]')
            city_btn = browser.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/ul[2]/li[1]/a')
            city_btn.click()
            sleep(4)
            br_city = browser.find_element(By.XPATH,
                                           '//*[@id="fancybox-content"]/div/div/div/div[1]/ul[2]/li[1]/div/a')
            br_city.click()
            sleep(2)
            br_city_select = browser.find_element(By.XPATH,
                                                  '//*[@id="fancybox-content"]/div/div/div/div[2]/ul[3]/li[1]/div/a')
            br_city_select.click()
            sleep(4)
            ActionChains(browser).send_keys(Keys.ESCAPE).perform()
            sleep(2)
            for art in self.articles_with_catalog:
                if art in self.update_arts:
                    continue
                else:
                    if re.search(r'\d{3}', art):
                        try:
                            browser.get(self.__main_url + art)
                            soup = BeautifulSoup(browser.page_source, 'lxml')
                            registration = soup.find('div', class_='registrationHintDescription')
                            if registration:
                                print(f'БАН! Крайний артикул: {art}')
                                browser.close()
                                browser.quit()
                                if soup_check.get('proxy') == '':
                                    return {'status': 'БАН', 'last_art': art[14:], 'baned_proxy': 'WITHOUT_PROXY'}
                                else:
                                    return {'status': 'БАН', 'last_art': art[14:],
                                            'baned_proxy': soup_check.get('proxy')}
                            current_art = f'goods_{art[14:]}'
                            self.update_arts.append(art)
                            self.check_attr_by_soup(soup, current_art)
                            time.sleep(0.5)
                            print(art)
                        except Exception as exp:
                            print(f'Прокси: {soup_check.get("proxy")} перестал отвечать во время работы.')
                            browser.close()
                            browser.quit()
                            if soup_check.get('proxy') == '':
                                return {'status': 'БАН', 'last_art': art[14:], 'baned_proxy': 'WITHOUT_PROXY'}
                            else:
                                return {'status': 'БАН', 'last_art': art[14:],
                                        'baned_proxy': soup_check.get('proxy')}
                    else:
                        print(art[14:])

            # browser.close()
            return {'status': 'OK', 'last_art': self.articles_with_catalog[-1]}
        elif soup_check.get('status') == 'ban':
            print('БАН на старте')
            if self.update_arts:
                return {'status': 'БАН', 'last_art': self.update_arts[-1][14:], 'baned_proxy': soup_check.get('proxy')}
            else:
                return {'status': 'БАН', 'last_art': 0, 'baned_proxy': soup_check.get('proxy')}
        elif soup_check.get('status') == 'Все прокси недоступны':
            if self.update_arts:
                return {'status': 'Все прокси недоступны', 'last_art': self.update_arts,
                        'baned_proxy': soup_check.get('proxy')}
            else:
                return {'status': 'Все прокси недоступны', 'last_art': 0, 'baned_proxy': 0}

    def add_empty_row(self):
        """Добавляем пустую строку"""
        pass

    def check_attr_by_soup(self, soup, current_art):
        check_list = []
        # current_art = f'goods_{art.split("/")[-1]}'
        if soup.find('div', class_='ProductState ProductState--red'):
            red_product_state = soup.find('div', class_='ProductState ProductState--red').text
            if red_product_state == 'Недоступен к\xa0заказу':
                check_list.append('-')
                print(f'Товар {current_art} недоступен к заказу')
        else:
            check_list.append('+')
        if soup.find('div', class_='Product__name'):
            if any(ext.lower() in soup.find('div', class_='Product__name').text.lower() for ext in self.bad_brand_list):
                check_list.append('-')
                print(f'Товар {current_art} из списка нежелательных брэндов')
            else:
                check_list.append('+')
        else:
            print()
        # if soup.find('div', class_='ProductState ProductState--gray'):
        #     min_count_str = soup.find('div', class_='ProductState ProductState--gray').text
        #     min_count = int(re.findall(r'\d+', min_count_str)[0])
        #     if min_count > 1:
        #         check_list.append('-')
        #         print(f'Минимальная партия более 1, а именно: {min_count}')
        #     else:
        #         check_list.append('+')
        if '-' not in check_list:
            print(f'Товар {current_art} проходит фильтры +')
            self.result_arts.append(current_art)
            self.get_attr_by_soup(soup)

    def get_attr_by_soup(self, soup):
        self.soup_list.append(soup)
        iteminfodetails = soup.find('div', class_='itemInfoDetails group')
        brand = json.loads(iteminfodetails.attrs['data-ga-obj']).get('brand')
        self.brand.append(brand)
        name = soup.find('div', class_='Product__name').text
        self.product_name.append(name)
        if soup.find('span', class_='Price Price--best'):
            price = float((soup.find('span', class_='Price Price--best').find('span', class_='Price__count').text +
                           '.' + soup.find('span', class_='Price Price--best').
                           find('span', class_='Price__penny').text).replace(' ', '').replace(u'\xa0', ''))
            self.price_discount_list.append(price)
        else:
            price = float(soup.find('span', class_='Price__count').text.replace(u'\xa0', '') + '.'
                          + soup.find('span', class_='Price__penny').text)
            self.price_discount_list.append(price)
        check_count_url_img = soup.find('ul', class_='ProductPhotoThumbs')
        if check_count_url_img:
            url = []
            main_url = [soup.find('ul', class_='ProductPhotoThumbs').find('li', class_='ProductPhotoThumb active').
                        find('a', href=True)['href']]
            surl = soup.find('ul', class_='ProductPhotoThumbs').findAll('li', class_='ProductPhotoThumb')
            video_present = False
            for su in surl:
                url_img = su.find('a', href=True)['href']
                if 'https://img.youtube.com/' in url_img:
                    youtube_url = soup.find('input', class_='js-productVideoID').attrs.get('value')
                    self.video_lst.append(youtube_url)
                    video_present = True
                else:
                    video_present = False
                    url.append(url_img)

            if not video_present:
                self.video_lst.append('-')

            url_str = ' '.join(url[1:17])
            self.url_img_add_list.append(url_str)
            main_url_str = ''.join(main_url)
            self.url_main_img_add_list.append(main_url_str)
        elif check_count_url_img is None:
            main_foto = soup.find('span', class_='main js-photoTarget').find('a', href=True)['href']
            # url_from_main_parse = df['Ссылка на изображение'].to_list()[u]
            self.url_main_img_add_list.append(main_foto)
            self.url_img_add_list.append('-')
            self.video_lst.append('-')
        tabscontent = soup.find('div',
                                class_='tabsContent js-tabsContent js-tabsContentMobile')  # общая таблица внизу
        description = tabscontent.find('div', class_='infoDescription').text.replace('\nОписание\n\n', '')
        description_split = description.split('.')
        for d in description_split:
            for r in self.remove_from_description:
                if r in d:
                    description_split.remove(d)
        description_result = '.'.join(description_split)
        self.description_list.append(description_result)
        shops = tabscontent.find('div', class_='tabsContent__item pickup'). \
            find('table', class_='AvailabilityList AvailabilityList--dotted'). \
            findAll('td', 'AvailabilityBox')
        krasnoarmeyskaya = shops[1].text
        if 'заказ' in krasnoarmeyskaya:
            krasnoarmeyskaya = 0
        elif 'Поступит' in krasnoarmeyskaya:
            krasnoarmeyskaya = 0
        else:
            krasnoarmeyskaya = int(krasnoarmeyskaya.replace('шт', '').replace(' ', '').replace('.', ''))
        sovetskaya = shops[3].text
        if 'заказ' in sovetskaya:
            sovetskaya = 0
        elif 'Поступит' in sovetskaya:
            sovetskaya = 0
        else:
            sovetskaya = int(sovetskaya.replace('шт', '').replace(' ', '').replace('.', ''))
        self.krasnoarmeyskaya_list.append(krasnoarmeyskaya)
        self.sovetskaya_list.append(sovetskaya)

        features = tabscontent.find('ul', class_='infoFeatures')  # общий раздел характеристики
        li_set = features.find_all('li')
        l = len(li_set)
        find_colour = False
        for i in li_set:
            # print(i.text)
            if 'Цвет — ' in i.text:
                self.features_colour_list.append(i.text.replace('Цвет — ', '')[:-1])
                find_colour = True
            # if any('Цвет — ' in s for s in li_set):
            #     if 'Цвет — ' in i.text:
            #         features_colour_list.append(i.text.replace('Цвет — ', '')[:-1])
            # else:
            #     features_colour_list.append('-')
            if 'Вес с упаковкой' in i.text:
                weight = i.text.replace('Вес с упаковкой', '').replace('\n', '').replace(' ', '').replace('—', '')
                if 'кг' in weight:
                    weight = int((float(weight.replace('кг', '').replace(',', '.')) * 1000))
                    self.features_package_weight_list.append(weight)
                else:
                    weight = int(weight.replace('г', ''))
                    self.features_package_weight_list.append(weight)
            elif 'Размер в упаковке' in i.text:
                string = i.text.replace('Размер в упаковке', '').replace('\n', '').replace('—', '').replace(' ', '')
                if 'см' in string:
                    string = string.replace('см', '')
                    length = int(float(string.split('x')[0]) * 10)
                    width = int(float(string.split('x')[1]) * 10)
                    height = int(float(string.split('x')[2]) * 10)
                    self.features_package_length_list.append(length)
                    self.features_packing_width_list.append(width)
                    self.features_packing_height_list.append(height)
                else:
                    print(f'Ошибка: в строке \n\n{i.text}\n\nв разделе размер нет см')
            elif 'Производитель — ' in i.text:
                manufacturer = i.text.replace('Производитель — ', '').replace(' ', '').replace('\n', '')
                self.features_manufacturer_list.append(manufacturer)
        if not find_colour:
            self.features_colour_list.append('-')
        # time.sleep(3)

    def create_df(self):
        self.df_each_product.insert(0, 'Артикул', self.result_arts)
        self.df_each_product.insert(1, 'Название', self.product_name)
        self.df_each_product.insert(2, 'Цена ОФИСМАГ', self.price_discount_list)
        self.df_each_product.insert(3, 'Цена для OZON', [390 if x * 3 < 390 else round(x * 3) for x
                                                         in self.price_discount_list])
        self.df_each_product.insert(4, 'Общий остаток', [self.sovetskaya_list[i] + self.krasnoarmeyskaya_list[i]
                                                         for i in range(len(self.krasnoarmeyskaya_list))])
        self.df_each_product.insert(5, 'Остаток на Советской', self.sovetskaya_list)
        self.df_each_product.insert(6, 'Остаток на Красноармейской', self.krasnoarmeyskaya_list)
        self.df_each_product.insert(7, 'Брэнд', self.brand)
        self.df_each_product.insert(8, 'Описание', self.description_list)
        self.df_each_product.insert(9, 'Цвет', self.features_colour_list)
        self.df_each_product.insert(10, 'Вес в упаковке (г)', self.features_package_weight_list)
        self.df_each_product.insert(11, 'Ширина в упаковке (мм)', self.features_packing_width_list)
        self.df_each_product.insert(12, 'Высота упаковки (мм)', self.features_packing_height_list)
        self.df_each_product.insert(13, 'Длина упаковки (мм)', self.features_package_length_list)
        self.df_each_product.insert(14, 'Производитель', self.features_manufacturer_list)
        self.df_each_product.insert(15, 'Ссылка на главное фото товара', self.url_main_img_add_list)
        self.df_each_product.insert(16, 'Ссылки на фото товара', self.url_img_add_list)
        # self.df_each_product.insert(17, 'Ссылка на видео товара', self.video_lst)

    def start(self):
        data = self.set_city_and_get_data()
        if data.get('status') == 'БАН' and data.get('baned_proxy') == '':
            self.baned_proxy.append('WITHOUT_PROXY')
            self.start()
        elif data.get('status') == 'БАН':
            self.baned_proxy.append(data.get('baned_proxy'))
            self.start()
        elif data.get('status') == 'Все прокси недоступны' and data.get('last_art') == 0:
            print('Парс ни разу не отработал')
        elif data.get('status') == 'Все прокси недоступны' and data.get('last_art') != 0:
            first_art = self.articles_with_catalog[0][14:]
            last_art = data.get("last_art")[-1][14:]
            if self.result_arts:
                self.create_df()
                current_date = date.today()
                XLS().create_from_one_df(self.df_each_product, 'Товары',
                                         f'update_arts_{first_art}_{last_art}_{current_date}')
        elif data.get('status') == 'OK':
            first_art = self.articles_with_catalog[0][14:]
            last_art = data.get("last_art")[14:]
            self.create_df()
            current_date = date.today()
            XLS().create_from_one_df(self.df_each_product, 'Товары',
                                     f'update_arts_{first_art}_{last_art}_{current_date}')


class CatalogABC:
    def __init__(self):
        self.url_abc = 'https://www.officemag.ru/catalog/abc/'

    def get_catalog(self):
        try:
            r = requests.get(self.url_abc, timeout=10.5)
            soup = BeautifulSoup(r.text, 'lxml')
            catalog = soup.find('ul', class_='catalogAlphabetList')
            print()
        except Exception as exp:
            print(exp)


class Catalog:
    def __init__(self, catalog_url_list, name_list):
        self.add_url = '?SORT=SORT&COUNT=60&PAGEN_1='
        self.catalog_url = catalog_url_list
        self.name_list = name_list
        self.res_list = []
        self.save_path = f'{str(Path(__file__).parents[1])}\\officemag_parser\\result'
        self.__main_url = 'https://www.officemag.ru'
        self.options = Options()
        self.options.add_argument("--start-maximized")
        self.service = Service('chromedriver.exe')

    def set_city(self):
        browser = webdriver.Chrome(service=self.service, options=self.options)
        browser.get(self.__main_url)
        city_btn = browser.find_element(By.XPATH, '/html/body/div[2]/div[1]/div/ul[2]/li[1]/a')
        city_btn.click()
        sleep(4)
        br_city = browser.find_element(By.XPATH,
                                       '//*[@id="fancybox-content"]/div/div/div/div[1]/ul[2]/li[1]/div/a')
        br_city.click()
        sleep(2)
        br_city_select = browser.find_element(By.XPATH,
                                              '//*[@id="fancybox-content"]/div/div/div/div[2]/ul[3]/li[1]/div/a')
        br_city_select.click()
        sleep(4)
        ActionChains(browser).send_keys(Keys.ESCAPE).perform()
        sleep(2)
        return browser

    def get_soup_by_catalog_from_browser(self, browser, url_cat, page):
        url = (self.__main_url + url_cat + self.add_url + str(page))
        browser.get(url)
        soup = BeautifulSoup(browser.page_source, 'lxml')
        return soup

    # def get_articles_by_soup(self, soup):
    #     status = True
    #     page = 1
    #     while status:
    #         if soup.find('div', class_='itemsNotFound'):
    #             status = False
    #         else:
    #             print(f'page={page}')
    #             page += 1
    #             listitems = soup.findAll('li', class_='js-productListItem')
    #             for l_it in listitems:
    #                 str_id = listitems[l_it].attrs.get('data-ga-obj')
    #                 id = ast.literal_eval(str_id).get('id')
    #                 self.res_list.append(id)

    def get_articles(self, browser, url_cat):
        status = True
        page = 1
        while status:
            time.sleep(1)
            soup = self.get_soup_by_catalog_from_browser(browser, url_cat=url_cat, page=page)
            if soup.find('div', class_='itemsNotFound') or soup.find('div', class_='registrationHintDescription'):
                status = False
            else:
                print(f'page={page}')
                page += 1
                listitems = soup.findAll('li', class_='js-productListItem')
                for l_it in enumerate(listitems):
                    str_id = listitems[l_it[0]].attrs.get('data-ga-obj')
                    id = ast.literal_eval(str_id).get('id')
                    self.res_list.append(id)

    def start(self):
        soup_check = ParseEachProduct().check_ban()
        if soup_check.get('status') == 'OK':
            if soup_check.get('city') == 'Брянск':
                pass
            else:
                print(f'Выбран город {soup_check.get("city")}, меняем на Брянск')
                browser = self.set_city()
                for i in enumerate(self.catalog_url):
                    print(self.name_list[i[0]])
                    self.res_list.append(self.name_list[i[0]])  # Добавляем имя категории
                    self.get_articles(browser, url_cat=i[1])
                    # soup = self.get_soup_by_catalog_from_browser(browser, url_cat=i[1])
        else:
            print('БАН')
        return self.res_list


def parse_discont_items():
    """Парсер раздела УСПЕЙ КУПИТЬ ВЫГОДНО. На выходе xls. Делается с 1 числа нового месяца"""
    ParseDiscontProduct().get_list_items()


def get_each_product():
    """Актуализация остатков из файла xls"""
    discont_product_df = XLS().read_xls_to_pd()
    ParseEachProduct().get_attr_each_product(df=discont_product_df)


def parse_actual_goods():
    """Парсим товары перебором по его id. Если товар существует, добавляем его артикул в текстовый файл"""
    with open('input\\proxy_file_checked.txt', 'r') as proxy_file:
        proxy_list = proxy_file.read().split('\n')
    actual_catalog_list = ActualCatalog(proxy_list).get_catalog_status(from_number=2761, to_number=3000)
    if actual_catalog_list:
        WriteFile(values=actual_catalog_list).write_txt_file_catalog_status()
        print(f'Успешно добавлено артикулов: {len(actual_catalog_list)}')
        print(actual_catalog_list)
    else:
        print('Нет активных товаров в указанном диапазоне')


def get_each_product_from_txt():
    """Актуализация остатков из файла txt. На выходе полная таблица xls."""
    with open('input\\articles_for_updating.txt', 'r', encoding="utf-8") as file:
        articles_with_catalog = [f'catalog/goods/{line.rstrip()}' for line in file]  # 'catalog/goods/621130'
        arts = [f'goods_{x[14:]}' for x in articles_with_catalog]  # 'goods_621130'
    SeleniumParse(articles_with_catalog, arts).start()


def get_articles_by_catalog():
    """Получаем из ссылки с каталогом список артикулов на странице, затем идет перебор страниц.
    На вход: файл abc.xls, на выходе: articles_with_name_category"""
    df = XLS().read_xls_to_pd(path_to_file='input\\abc.xlsx', sheet_name='Лист1')
    catalog_url_list = df['Каталог'].to_list()
    name_list = df['Название'].to_list()
    res_list = Catalog(catalog_url_list=catalog_url_list, name_list=name_list).start()
    WriteFile(values=res_list).write_txt_articles_and_names()


def main():
    get_each_product_from_txt()


if __name__ == '__main__':
    main()
