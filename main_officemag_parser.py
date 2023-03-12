"""Парсер магазина officemag (https://www.officemag.ru/)"""

import requests
import time
from bs4 import BeautifulSoup
from tqdm import tqdm


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
    def __init__(self):
        self.first_page = 'https://www.officemag.ru/promo/actions/?action_kind=manual&SORT=SORT&COUNT=60&PAGEN_1=2'


def parse_actual_goods():
    """Парсим товары перебором по его id. Если товар существует, добавляем ссылку на него в текстовый файл"""
    actual_catalog_list = ActualCatalog().get_catalog_status(from_number=3000, to_number=3010)
    WriteFile(values=actual_catalog_list).write_txt_file_catalog_status()
    print()


def main():
    parse_actual_goods()


if __name__ == '__main__':
    main()
