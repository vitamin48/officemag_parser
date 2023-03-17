"""Парсер магазина officemag (https://www.officemag.ru/)"""
import re
from pathlib import Path
import requests
import time
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

from urllib.request import urlopen as uReq
import json


class WriteFile:
    def __init__(self, values):
        self.values = values

    def write_txt_file_catalog_status(self):
        with open("catalog_status_officemag.txt", "w") as output:
            for row in self.values:
                output.write(str(row) + '\n')


class ActualCatalog:
    def __init__(self):
        self.catalog = 'https://www.officemag.ru/catalog/'

    def get_catalog_status(self, from_number, to_number):
        actual_catalog_list = []
        url = ''
        for i in tqdm(range(from_number, to_number)):
            r = requests.get(self.catalog + f'{i}')
            soup = BeautifulSoup(r.text, 'lxml')
            sort = soup.find('div', class_='sort')
            registration = soup.find('div', class_='registrationHintDescription')
            if registration:
                print('БАН')
                return actual_catalog_list
            if sort:
                url = self.catalog + f'{i}'
                actual_catalog_list.append(url)
                print(f'i = {i}, \n {url}')
            # time.sleep(1)
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

    def get_attr_each_product(self, df):
        description_list = []  # описание
        features_colour_list = []  # цвет
        features_package_weight_list = []  # вес в упаковке
        features_package_length_list = []  # Длина упаковки
        features_packing_width_list = []  # ширина в упаковке
        features_packing_height_list = []  # Высота упаковки

        features_manufacturer_list = []  # Производитель
        url_add_list = []  # дополнительные ссылки на товар из карточки
        price_discont_list = []  # цена с учетом скидки
        krasnoarmeyskaya_list = []
        sovetskaya_list = []

        url_list = df['URL'].tolist()
        fr = 76
        to = 100
        for u in range(76, 100):
            # for u in range(len(url_list)):
            code = url_list[u][1:]
            print(f'code ======{code}')
            soup = self.get_soup(code=code)
            price = float((soup.find('span', class_='Price Price--best').find('span', class_='Price__count').text +
                           '.' + soup.find('span', class_='Price Price--best').
                           find('span', class_='Price__penny').text).replace(' ', '').replace(u'\xa0', ''))
            price_discont_list.append(price)
            check_count_url_img = soup.find('ul', class_='ProductPhotoThumbs')
            if check_count_url_img:
                url = [soup.find('ul', class_='ProductPhotoThumbs').find('li', class_='ProductPhotoThumb active').
                       find('a', href=True)['href']]
                surl = soup.find('ul', class_='ProductPhotoThumbs').findAll('li', class_='ProductPhotoThumb')
                for su in surl:
                    url.append(su.find('a', href=True)['href'])
                url_str = ' '.join(url)
                url_add_list.append(url_str)
            elif check_count_url_img is None:
                url_from_main_parse = df['Ссылка на изображение'].to_list()[u]
                url_add_list.append(url_from_main_parse)
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
        df_each_product.insert(0, 'Code', url_list[fr:to])
        df_each_product.insert(1, 'Название', df['Название'].to_list()[fr:to])
        df_each_product.insert(2, 'Цена со скидкой', price_discont_list)
        df_each_product.insert(3, 'Актуальный остаток на Советской', sovetskaya_list)
        df_each_product.insert(4, 'Предыдущий остаток на Советской', df['Остаток на Советской'].to_list()[fr:to])
        df_each_product.insert(5, 'Актуальный остаток на Красноармейской', krasnoarmeyskaya_list)
        df_each_product.insert(6, 'Предыдущий остаток на Красноармейской',
                               df['Остаток на Красноармейской'].to_list()[fr:to])
        df_each_product.insert(7, 'Описание', description_list)
        df_each_product.insert(8, 'Цвет', features_colour_list)
        df_each_product.insert(9, 'Вес в упаковке (г)', features_package_weight_list)
        df_each_product.insert(10, 'Длина упаковки (мм)', features_package_length_list)
        df_each_product.insert(11, 'Ширина в упаковке (мм)', features_packing_width_list)
        df_each_product.insert(12, 'Высота упаковки (мм)', features_packing_height_list)
        df_each_product.insert(13, 'Производитель', features_manufacturer_list)
        df_each_product.insert(14, 'Ссылки на фото товара', url_add_list)
        XLS().create_from_one_df(df_each_product, 'Товары', 'res_parse_product')


class XLS:
    def __init__(self):
        self.save_path = f'{str(Path(__file__).parents[1])}\\officemag_parser'
        self.path_res_parse = f'{str(Path(__file__).parents[1])}\\officemag_parser\\res_parse.xlsx'

    def create_from_one_df(self, df, sheet, file_name):
        """Создание файла excel из 1-го DataFrame"""
        path = f'{self.save_path}\\{file_name}.xlsx'
        writer = pd.ExcelWriter(path, engine_kwargs={'options': {'strings_to_urls': False}})
        df.to_excel(writer, sheet_name=sheet, index=False, na_rep='NaN', engine='openpyxl')
        # Auto-adjust columns' width
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column)) + 2
            col_idx = df.columns.get_loc(column)
            writer.sheets[f'{sheet}'].set_column(col_idx, col_idx, column_width)
        writer.sheets[sheet].set_column(1, 1, 30)
        writer.sheets[sheet].set_column(7, 7, 30)
        writer.sheets[sheet].set_column(14, 14, 30)
        writer.close()
        return path

    def read_xls_to_pd(self):
        discont_product_df = pd.read_excel(self.path_res_parse, sheet_name='Товары со скидками')
        return discont_product_df


def parse_actual_goods():
    """Парсим товары перебором по его id. Если товар существует, добавляем ссылку на него в текстовый файл"""
    actual_catalog_list = ActualCatalog().get_catalog_status(from_number=4000, to_number=4005)
    WriteFile(values=actual_catalog_list).write_txt_file_catalog_status()


def parse_discont_items():
    """Парсер раздела УСПЕЙ КУПИТЬ ВЫГОДНО. На выходе xls"""
    ParseDiscontProduct().get_list_items()


def get_each_product():
    discont_product_df = XLS().read_xls_to_pd()
    ParseEachProduct().get_attr_each_product(df=discont_product_df)


def main():
    get_each_product()


if __name__ == '__main__':
    main()
