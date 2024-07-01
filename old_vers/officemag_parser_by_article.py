import os
import sys
import time
import re
import json
from datetime import date
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver import ActionChains
import pandas as pd
from bs4 import BeautifulSoup
from tqdm import tqdm


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


class SeleniumParse:
    def __init__(self, articles_with_catalog, arts):
        self.save_path = f'{str(Path(__file__).parents[1])}\\officemag_parser'
        self.__main_url = 'https://www.officemag.ru/'
        self.options = Options()
        self.options.add_argument("--start-maximized")
        self.service = Service('../chromedriver.exe')
        # self.browser = webdriver.Chrome(service=self.service, options=self.options)
        self.soup_list = []
        self.articles_with_catalog = articles_with_catalog
        self.arts = arts
        self.baned_proxy = []
        self.bad_brand_list = ['Lavazza', 'BRAUBERG', 'DURACELL', 'SYNERGETIC', 'SONNEN', 'JACOBS', 'ГАММА', 'KITFORT',
                               'DEFENDER', 'XIAOMI', 'SVEN', 'LOGITECH', 'ЧЕРНОГОЛОВКА', 'СЕНЕЖСКАЯ', 'СВЯТОЙ ИСТОЧНИК',
                               'BORJOMI', 'KINGSTON', 'CANON', 'HP', 'CASIO']
        self.remove_from_description = ['в нашем интернет-магазине', 'у нас на сайте']
        self.update_arts = []  # список отработанных артикулов
        self.df_each_product = pd.DataFrame()

        self.open_vpn = OpenVPN()

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

    def set_city_and_get_data_over_vpn(self):
        self.options.add_argument('--blink-settings=imagesEnabled=false')
        browser = webdriver.Chrome(service=self.service, options=self.options)
        browser.set_page_load_timeout(59)
        try:
            browser.get('https://ipinfo.io/json')
            browser.get(self.__main_url)
            browser.implicitly_wait(15)
            city_btn = browser.find_element(By.XPATH, '/html/body/div[3]/div[1]/div/ul[2]/li[1]/a')
            city_btn.click()
            time.sleep(4)
            br_city = browser.find_element(By.XPATH,
                                           '//*[@id="fancybox-content"]/div/div/div/div[1]/ul[2]/li[1]/div/a')
            br_city.click()
            time.sleep(2)
            br_city_select = browser.find_element(By.XPATH,
                                                  '//*[@id="fancybox-content"]/div/div/div/div[2]/ul[3]/li[1]/div/a')
            br_city_select.click()
            time.sleep(4)
            ActionChains(browser).send_keys(Keys.ESCAPE).perform()
            time.sleep(2)
            for art in tqdm(self.articles_with_catalog):
                current_art = f'goods_{art[14:]}'
                if current_art in self.update_arts:
                    continue
                else:
                    if re.search(r'\d{3}', art):
                        try:
                            browser.get(self.__main_url + art)
                            browser.implicitly_wait(40)
                            time.sleep(0.1)
                            soup = BeautifulSoup(browser.page_source, 'lxml')
                            registration = soup.find('div', class_='registrationHintDescription')
                            if registration:
                                print(f'{bcolors.FAIL}БАН VPN!Крайний артикул:{self.update_arts[-1]}{bcolors.ENDC}')
                                browser.close()
                                browser.quit()
                                return {'status': 'ban_vpn'}
                            self.update_arts.append(current_art)
                            self.check_attr_by_soup(soup, current_art, art=art)
                        except Exception as exp:
                            print(f'{bcolors.FAIL}VPN перестал отвечать во время работы.{bcolors.ENDC}')
                            print(exp)
                            print('=' * 50)
                            browser.close()
                            browser.quit()
                            return {'status': 'ban_vpn'}
                    else:
                        print(f'{bcolors.OKGREEN}{art[14:]}{bcolors.ENDC}')
            return {'status': 'Finish'}
        except Exception as exp:
            print(
                f'{bcolors.FAIL}VPN перестал отвечать во время установки города.{bcolors.ENDC}')
            print(exp)
            browser.close()
            browser.quit()
            return {'status': 'ban_vpn'}

    def check_attr_by_soup(self, soup, current_art, art):
        if len(self.result_arts) == len(self.product_name) == len(self.price_discount_list) == \
                len(self.sovetskaya_list) == len(self.krasnoarmeyskaya_list) == len(self.brand) == \
                len(self.description_list) == len(self.features_colour_list) == len(self.features_package_weight_list) \
                == len(self.features_packing_width_list) == len(self.features_packing_height_list) == \
                len(self.features_package_length_list) == len(self.features_manufacturer_list) == \
                len(self.url_main_img_add_list) == len(self.url_img_add_list):
            check_list = []
            # if soup.find('div', class_='ProductState ProductState--red'):
            #     red_product_state = soup.find('div', class_='ProductState ProductState--red').text
            #     if red_product_state == 'Недоступен к\xa0заказу':
            #         check_list.append('-')
            #         print(f'{bcolors.WARNING}Товар {current_art} недоступен к заказу{bcolors.ENDC}')
            # else:
            #     check_list.append('+')
            if soup.find('div', class_='Product__name'):
                if any(ext.lower() in soup.find('div', class_='Product__name').text.lower() for ext in
                       self.bad_brand_list):
                    check_list.append('-')
                    print(f'{bcolors.WARNING}Товар {current_art} из списка нежелательных брэндов{bcolors.ENDC}')
                else:
                    check_list.append('+')
            else:
                print(f'{bcolors.WARNING}Product__name отсутствует{bcolors.ENDC}')
                check_list.append('-')
            for removed_art in soup.findAll('div', class_='ProductState ProductState--red'):
                if removed_art.text == 'Выведен из\xa0ассортимента':
                    print(f'{bcolors.WARNING}Товар {current_art} выведен из ассортимента{bcolors.ENDC}')
                    check_list.append('-')
                elif removed_art.text == 'Недоступен к\xa0заказу':
                    print(f'{bcolors.WARNING}Товар {current_art} недоступен к заказу{bcolors.ENDC}')
                    check_list.append('-')
            if '-' not in check_list:
                print(f'Товар {current_art} проходит фильтры +')
                # self.update_arts.append(art)
                self.result_arts.append(current_art)
                self.get_attr_by_soup(soup)
        else:
            print('Количество значений не одинаково!')
            print('result_arts=', len(self.result_arts))
            print('product_name=', len(self.product_name))
            print('price_discount_list=', len(self.price_discount_list))
            print('sovetskaya_list=', len(self.sovetskaya_list))
            print('krasnoarmeyskaya_list=', len(self.krasnoarmeyskaya_list))
            print('brand=', len(self.brand))
            print('description_list=', len(self.description_list))
            print('features_colour_list=', len(self.features_colour_list))
            print('features_package_weight_list=', len(self.features_package_weight_list))
            print('features_packing_width_list=', len(self.features_packing_width_list))
            print('features_packing_height_list=', len(self.features_packing_height_list))
            print('features_package_length_list=', len(self.features_package_length_list))
            print('features_manufacturer_list=', len(self.features_manufacturer_list))
            print('url_main_img_add_list=', len(self.url_main_img_add_list))
            print('url_img_add_list=', len(self.url_img_add_list))
            sys.exit()

    def get_attr_by_soup(self, soup):
        self.soup_list.append(soup)
        iteminfodetails = soup.find('div', class_='itemInfoDetails group')
        brand = json.loads(iteminfodetails.attrs['data-ga-obj']).get('brand')
        self.brand.append(brand)
        name = soup.find('div', class_='Product__name').text
        self.product_name.append(name)
        price_div = soup.find('div', class_='Product__priceWrapper')
        if price_div.find('span', class_='Price Price--best'):
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
        li_list = list(li_set)
        if not [x for x in li_list if 'Размер в упаковке' in x.text]:
            print(f'{bcolors.WARNING}Параметр Размер в упаковке отсутствует!{bcolors.ENDC}')
            self.features_package_length_list.append('-')
            self.features_packing_width_list.append('-')
            self.features_packing_height_list.append('-')
        find_colour = False
        all_manuf = []
        for manuf in li_set:
            if 'Производитель — ' in manuf.text:
                all_manuf.append(manuf.text)
        manufacturer = all_manuf[-1].replace('Производитель —', '').replace(' ', '').replace('\n', '')
        self.features_manufacturer_list.append(manufacturer)
        for i in li_set:
            if 'Цвет — ' in i.text:
                self.features_colour_list.append(i.text.replace('Цвет — ', '')[:-1])
                find_colour = True
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
        if not find_colour:
            self.features_colour_list.append('-')

    def create_df(self):
        try:
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
        except Exception as exp:
            print(f'Error DF: \n {exp}')

    def start(self):
        # vpn_status = OpenVPN().get_connect()
        vpn_status = self.open_vpn.get_connect()
        if vpn_status.get('status') == 'connect':
            selen = self.set_city_and_get_data_over_vpn()
            if selen.get('status') == 'ban_vpn':
                self.start()
            elif selen.get('status') == 'Finish':
                self.create_df()
                current_date = date.today()
                last_art = ''
                if len(self.result_arts) > 0:
                    last_art = self.result_arts[-1][5:]
                XLS().create_from_one_df(self.df_each_product, 'Товары',
                                         f'offmag_{self.articles_with_catalog[0][14:]}_'
                                         f'{last_art}_{current_date}')
        elif vpn_status.get('status') == 'ended_vpn':
            self.create_df()
            current_date = date.today()
            last_art = ''
            if len(self.result_arts) > 0:
                last_art = self.result_arts[-1][5:]
            XLS().create_from_one_df(self.df_each_product, 'Товары',
                                     f'offmag_{self.articles_with_catalog[0][14:]}_'
                                     f'{last_art}_{current_date}')


class OpenVPN:
    def __init__(self):
        self.path_bin = 'C:\\Program Files\\OpenVPN\\bin\\openvpn-gui.exe'
        self.path_config = os.path.expanduser('~') + '\\OpenVPN\\config\\'
        self.path_logs = os.path.expanduser('~') + '\\OpenVPN\\log\\'
        self.dir_list_config = os.listdir(self.path_config)
        self.dir_list_logs = os.listdir(self.path_logs)
        self.connect_msg = 'Initialization Sequence Completed'
        self.disconnect_msg = 'SIGTERM[hard,] received, process exiting'
        self.used_vpn = []

    def get_connect(self):
        os.system(rf'"C:\Program Files\OpenVPN\bin\openvpn-gui.exe" --command disconnect_all')
        for cnf in enumerate(self.dir_list_config):
            if cnf[1] in self.used_vpn:
                continue
            else:
                print(f'TRY connect to VPN: {cnf}')
                os.system(rf'"C:\Program Files\OpenVPN\bin\openvpn-gui.exe" --command connect {cnf[1]}')
                time.sleep(30)
                with open(self.path_logs + self.dir_list_logs[cnf[0]], 'r') as log:
                    for line in log:
                        if self.connect_msg in line:
                            print(line.strip())
                            print(f'{bcolors.OKGREEN}connect to VPN: {cnf}{bcolors.ENDC}')
                            self.used_vpn.append(cnf[1])
                            return {'status': 'connect', 'index_vpn': self.dir_list_config.index(cnf[1]),
                                    'name_vpn': self.dir_list_config[cnf[0]]}
                os.system(rf'"C:\Program Files\OpenVPN\bin\openvpn-gui.exe" --command disconnect {cnf[1]}')
                continue
        print('ended_vpn')
        return {'status': 'ended_vpn'}


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


def main():
    with open('input\\articles_for_updating.txt', 'r', encoding="utf-8") as file:
        articles_with_catalog = [f'catalog/goods/{line.rstrip()}' for line in file]  # 'catalog/goods/621130'
        arts = [f'goods_{x[14:]}' for x in articles_with_catalog]  # 'goods_621130'
    SeleniumParse(articles_with_catalog, arts).start()


if __name__ == '__main__':
    main()
