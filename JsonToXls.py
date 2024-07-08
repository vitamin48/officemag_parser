"""
Скрипт считывает файл JSON с товарами Офисмаг и записывает данные в Excel.
"""
import json
import re
import pandas as pd

from openpyxl.utils import get_column_letter

FILE_NAME_JSON = 'result/data_1.json'


def read_json():
    with open(FILE_NAME_JSON, 'r', encoding='utf-8') as json_file:
        data = json.load(json_file)
        return data


def read_bad_brand():
    """Считывает и возвращает список нежелательных брендов"""
    with open('input/bad_brand.txt', 'r', encoding='utf-8') as file:
        brands = [line.strip().lower() for line in file if line.strip()]
    return set(brands)


def check_key_in_dict(key):
    check_list = ['NO_KEY_brand', 'NO_KEY_country']
    if key in check_list:
        input(key)


def create_df_by_dict(data_dict):
    rows = []
    # Проходим по каждому ключу в словаре
    for key, value in data_dict.items():
        brand = value.get('brand', 'NO_KEY')
        name = value.get('name')
        # Обработка характеристик
        characteristics = value.get("characteristics", {})
        country = characteristics.get('Производитель', 'NO_KEY')
        # Обработка Высота х Длина х Ширина
        dimensions = characteristics.get('Размер в упаковке', 'NO_KEY')
        modified_dimensions = re.sub(r'\s*см', '', dimensions)
        height, length, width = map(lambda x: round(float(x) * 10), modified_dimensions.split('x'))
        print()
    print()


if __name__ == '__main__':
    data_json = read_json()
    excluded_brands = read_bad_brand()
    create_df_by_dict(data_dict=data_json)
    print()
    # df = create_df_by_dict(data_dict=data_json)
    # create_xls(df)
