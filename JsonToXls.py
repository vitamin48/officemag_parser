"""
Скрипт считывает файл JSON с товарами Офисмаг и записывает данные в Excel.
"""
import json
import re
import pandas as pd

from openpyxl.utils import get_column_letter

FILE_NAME_JSON = 'old_vers/result/result_merge_data.json'


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


def transform_price(x):
    result = x * 5 if x < 200 else (
        x * 4.5 if 200 <= x < 500 else (
            x * 4 if 500 <= x < 1000 else (
                x * 3.5 if 1000 <= x < 5000 else (
                    x * 3 if 5000 <= x < 10000 else (
                        x * 2.5 if 10000 <= x < 20000 else (x * 2))))))
    # Убеждаемся, что значение после преобразований не меньше 490
    result = max(result, 490)
    # Округление до целого числа
    return round(result)


def create_rows_for_df_by_dict(data_dict):
    bad_brands = read_bad_brand()
    rows_main = []
    rows_stock = []
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
        "Вес"
        weight = characteristics.get('Вес с упаковкой', 'NO_KEY')
        if weight == 'NO_KEY':
            input(f'NO_KEY не найден вес для {key}')
        if 'кг' in weight:
            weight = weight.replace(',', '.').replace('кг', '').strip()
            weight = round(float(weight) * 1000)
        elif ' г' in weight:
            weight = weight.replace(',', '.').replace('г', '').strip()
            weight = int(weight)
        else:
            print()
        "Цена"
        price = value.get('price', 'NO_KEY')
        modified_price = round(float(re.sub(r'\s*', '', price)))
        # """Доп проверка, выбрать только те товары, в закупе которые стоят дороже 1900 р"""
        # if modified_price < 1900:
        #     continue
        "Остатки"
        stock = value.get('stock')
        warehouse_bryansk = extract_numbers(stock.get('Наличие на складе в Брянске', 0))
        remote_warehouse = extract_numbers(stock.get('Удаленный склад (срок поставки от 3 дней)',
                                                     stock.get('Удаленный склад (срок поставки от 5 рабочих дней)', 0)))
        krasnoarmeyskaya = extract_numbers(stock.get('г. Брянск, ул. Красноармейская, 93Б, ТЦ Профиль', 0))
        sovetskaya = extract_numbers(stock.get('г. Брянск, ул. Советская, д. 99', 0))
        bezhitsa = extract_numbers(stock.get('г. Брянск, ул. 3-го Интернационала, 13***СКОРО ОТКРЫТИЕ 15.07.2024', 0))
        """Дополнительное условие, если остатки товаров суммарно на Красноармейской и Советской равны 0, 
        то такие товары пропускаем, либо нет"""
        if krasnoarmeyskaya + sovetskaya == 0:
            continue
        # if warehouse_bryansk < 30:
        #     continue
        "Описание"
        description = value.get("description", "")
        description = description.replace('НДС: 20%', '').replace(' ', ' ')
        "Изображения"
        img_urls = value.get("img_urls", [])
        if isinstance(img_urls, str):
            img_urls = [img_urls]
        if len(img_urls) > 0:  # Извлечение первой ссылки и всех остальных
            img_url1 = img_urls[0]
            img_url2 = img_urls[1:]  # Все остальные ссылки
            # Преобразуем список ссылок в строку, разделенную запятой, или оставляем как есть.
            img_url2 = ", ".join(img_url2) if len(img_url2) > 0 else "-"
        else:
            img_url1 = "-"
            img_url2 = "-"
        "Формируем итоговую главную строку"
        row = {
            "ArtNumber": key,
            "Название": name,
            "Цена Офисмага": modified_price,
            "Описание": description,
            "Ссылка на главное фото товара": img_url1,
            "Ссылки на другие фото товара": img_url2,
            "art_url": value.get("art_url", ""),
            "Бренд": brand,
            "Страна": country,
            "Вес, г": weight,
            "Ширина, мм": width,
            "Высота, мм": height,
            "Длина, мм": length,
            "Характеристики": str(characteristics).replace('\\xa0', '')
        }
        "Формируем строку с остатками"
        row_stock = {
            "ArtNumber": f'goods_{key}',
            "Название": name,
            "Остатки Крс+Сов": krasnoarmeyskaya + sovetskaya,
            "Остатки на складе в Брянске": warehouse_bryansk,
            "Остатки на удаленном складе": remote_warehouse,
            "Остатки на Красноармейской": krasnoarmeyskaya,
            "Остатки на Советской": sovetskaya,
            "Остатки в Бежице": bezhitsa
        }
        rows_main.append(row)
        rows_stock.append(row_stock)
    return rows_main, rows_stock


def create_df_by_rows(rows_main, rows_stock):
    # Создание DataFrame из списка словарей
    df_main = pd.DataFrame(rows_main)
    df_stock = pd.DataFrame(rows_stock)
    # Добавляем артикул
    df_main["Артикул"] = df_main["ArtNumber"].apply(lambda art: f'goods_{art}')
    # Добавляем столбец Цена для OZON
    df_main['Цена для OZON'] = df_main['Цена Офисмага'].apply(transform_price)
    # Добавляем столбец Цена до скидки
    df_main['Цена до скидки'] = df_main['Цена для OZON'].apply(lambda x: int(round(x * 1.3)))
    # Добавляем столбец НДС Не облагается
    df_main["НДС"] = "Не облагается"
    # Задаем порядок столбцов
    desired_order = ['Артикул', 'Название', 'Цена для OZON', 'Цена до скидки', 'НДС', 'Цена Офисмага', 'Вес, г',
                     'Ширина, мм', 'Высота, мм', 'Длина, мм', 'Ссылка на главное фото товара',
                     'Ссылки на другие фото товара', 'Бренд', 'ArtNumber', 'Описание', 'Страна',
                     'Характеристики', 'art_url']
    result_main_df = df_main[desired_order]
    return result_main_df, df_stock


def create_xls(df_main, df_stock):
    file_name = f'old_vers/result\\OfficeMag.xlsx'
    # Сохранение DataFrame в Excel с использованием Styler
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
        df_main.to_excel(writer, sheet_name='Данные', index=False, na_rep='NaN')
        df_stock.to_excel(writer, sheet_name='Остатки', index=False, na_rep='NaN')
        "Работа с данными"
        # Установка ширины столбцов
        worksheet_ozon = writer.sheets['Данные']
        for column in df_main:
            column_width = max(df_main[column].astype(str).map(len).max(), len(column)) + 2
            col_letter = get_column_letter(df_main.columns.get_loc(column) + 1)
            worksheet_ozon.column_dimensions[col_letter].width = column_width
        # Закрепите первую строку
        worksheet_ozon.freeze_panes = 'A2'
        # Корректировка ширины столбцов
        worksheet_ozon.column_dimensions[get_column_letter(df_main.columns.get_loc('Название') + 1)].width = 30
        worksheet_ozon.column_dimensions[get_column_letter(df_main.columns.get_loc('Описание') + 1)].width = 30
        worksheet_ozon.column_dimensions[get_column_letter(df_main.columns.get_loc('Характеристики') + 1)].width = 30
        worksheet_ozon.column_dimensions[
            get_column_letter(df_main.columns.get_loc('Ссылка на главное фото товара') + 1)].width = 30
        worksheet_ozon.column_dimensions[
            get_column_letter(df_main.columns.get_loc('Ссылки на другие фото товара') + 1)].width = 30
        worksheet_ozon.column_dimensions[
            get_column_letter(df_main.columns.get_loc('art_url') + 1)].width = 20
        "Работа с остатками"
        worksheet_srock = writer.sheets['Остатки']
        for column in df_stock:
            column_width = max(df_stock[column].astype(str).map(len).max(), len(column)) + 2
            col_letter = get_column_letter(df_stock.columns.get_loc(column) + 1)
            worksheet_srock.column_dimensions[col_letter].width = column_width
        # Корректировка ширины столбцов
        worksheet_srock.column_dimensions[get_column_letter(df_main.columns.get_loc('Название') + 1)].width = 30


if __name__ == '__main__':
    data_json = read_json()
    excluded_brands = read_bad_brand()
    rows_main, rows_stock = create_rows_for_df_by_dict(data_dict=data_json)
    df_main, df_stock = create_df_by_rows(rows_main, rows_stock)
    create_xls(df_main, df_stock)
    print('Успешно!')
    # df = create_df_by_dict(data_dict=data_json)
    # create_xls(df)
