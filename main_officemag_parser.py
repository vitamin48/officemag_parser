"""Парсер магазина officemag (https://www.officemag.ru/)"""

import requests
import time
from bs4 import BeautifulSoup
from tqdm import tqdm


def write_txt_file_catalog_status(values):
    with open("catalog_status_officemag.txt", "w") as output:
        for row in values:
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
                break
            if sort:
                url = self.catalog + f'{i}'
                actual_catalog_list.append(url)
                print(f'i = {i}, \n {url}')
            #time.sleep(1)
        return actual_catalog_list


if __name__ == '__main__':
    actual_catalog_list = ActualCatalog().get_catalog_status(from_number=1000, to_number=2000)
    write_txt_file_catalog_status(values=actual_catalog_list)


