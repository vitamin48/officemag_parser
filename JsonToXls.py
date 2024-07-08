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


def contains_unwanted_brand(product_name, bad_brands):
    """Функция для проверки наличия нежелательных брендов в имени товара"""
    for brand in bad_brands:
        if brand in product_name.strip().lower():
            return True
    return False


def extract_numbers(input_string):
    return int(''.join([char for char in str(input_string) if char.isdigit()]))


def create_df_by_dict(data_dict):
    bad_brands = read_bad_brand()
    rows = []
    # Проходим по каждому ключу в словаре
    for key, value in data_dict.items():
        brand = value.get('brand', 'NO_KEY')
        if brand.strip().lower() in bad_brands:
            # input(f'{brand} - bad_brands в брендах')
            continue
        name = value.get('name')
        if contains_unwanted_brand(product_name=name, bad_brands=bad_brands):
            # input(f'{name} - bad_brands в имени')
            # print(f'Бренд:{brand}\nНазвание:{name}')
            continue
        """Обработка характеристик"""
        characteristics = value.get("characteristics", {})
        "Страна"
        country = characteristics.get('Производитель', 'NO_KEY')
        "Высота х Длина х Ширина"
        dimensions = characteristics.get('Размер в упаковке', 'NO_KEY')
        if dimensions == 'NO_KEY':
            height = length = width = 'NO_KEY'
        else:
            modified_dimensions = re.sub(r'\s*см', '', dimensions)
            height, length, width = map(lambda x: round(float(x) * 10), modified_dimensions.split('x'))
        "Цена"
        price = value.get('price', 'NO_KEY')
        modified_price = round(float(re.sub(r'\s*', '', price)))
        "Остатки"
        stock = value.get('stock')
        warehouse_bryansk = extract_numbers(stock.get('Наличие на складе в Брянске', 0))
        remote_warehouse = extract_numbers(stock.get('Удаленный склад (срок поставки от 3 дней)',
                                                     stock.get('Удаленный склад (срок поставки от 5 рабочих дней)', 0)))
        krasnoarmeyskaya = extract_numbers(stock.get('г. Брянск, ул. Красноармейская, 93Б, ТЦ Профиль', 0))
        sovetskaya = extract_numbers(stock.get('г. Брянск, ул. Советская, д. 99', 0))
        bezhitsa = extract_numbers(stock.get('г. Брянск, ул. 3-го Интернационала, 13***СКОРО ОТКРЫТИЕ 15.07.2024', 0))
        row = {
            "ArtNumber": key,
            "Название": name,
            "Цена Офисмага": modified_price,
            "Остатки": value.get("stock", ""),
            "Описание": value.get("description", ""),
            # "Ссылка на главное фото товара": img_url1,
            # "Ссылки на другие фото товара": img_url2,
            "art_url": value.get("art_url", ""),
            "Бренд": brand,
            "Страна": country,
            "Ширина, мм": width,
            "Высота, мм": height,
            "Длина, мм": length,
            "Характеристики": str(characteristics),
        }
        print()
    print()


if __name__ == '__main__':
    data_json = read_json()
    excluded_brands = read_bad_brand()
    create_df_by_dict(data_dict=data_json)
    print()
    # df = create_df_by_dict(data_dict=data_json)
    # create_xls(df)
