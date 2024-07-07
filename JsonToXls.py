"""
Скрипт считывает файл JSON с товарами Офисмаг и записывает данные в Excel.
"""
import json
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


def create_df_by_dict(data_dict):
    rows = []
    # Проходим по каждому ключу в словаре
    for key, value in data_dict.items():
        # Обработка характеристик
        characteristics = value.get("characteristics", {})


if __name__ == '__main__':
    data_json = read_json()
    excluded_brands = read_bad_brand()
    create_df_by_dict(data_dict=data_json)
    print()
    # df = create_df_by_dict(data_dict=data_json)
    # create_xls(df)
