"""
Скрипт считывает файл JSON с товарами и записывает данные в Excel.
Формируется 3 листа:
1. С товарами для маркетплейса (OZON)
2. Остатки по товарам в разрезе складов
3. Товары с нежелательными брендами
"""
import json
import pandas as pd
import re
from openpyxl.utils import get_column_letter

# --- НАСТРОЙКИ ---
FILE_NAME_JSON = 'out/products_data.json'
RESULT_FILE_NAME = 'out/Officemag.xlsx'
BAD_BRAND_FILE = 'in/bad_brand.txt'


def read_json():
    """Считывает и возвращает данные из JSON-файла."""
    try:
        with open(FILE_NAME_JSON, 'r', encoding='utf-8') as json_file:
            data = json.load(json_file)
            return data
    except FileNotFoundError:
        print(f"Ошибка: Файл {FILE_NAME_JSON} не найден.")
        return None
    except json.JSONDecodeError:
        print(f"Ошибка: Некорректный формат JSON в файле {FILE_NAME_JSON}.")
        return None


def read_bad_brand():
    """Считывает и возвращает список нежелательных брендов."""
    try:
        with open(BAD_BRAND_FILE, 'r', encoding='utf-8') as file:
            brands = [line.strip().lower() for line in file if line.strip()]
        return set(brands)
    except FileNotFoundError:
        print(
            f"Файл с нежелательными брендами {BAD_BRAND_FILE} не найден. Фильтрация по брендам не будет производиться.")
        return set()


def transform_price(x):
    """Преобразует цену по заданной логике."""
    if not isinstance(x, (int, float)):
        return 0
    if x < 100:
        result = x * 7
    elif x < 250:
        result = x * 6
    elif x < 500:
        result = x * 5
    elif x < 750:
        result = x * 4.5
    elif x < 1000:
        result = x * 4
    elif x < 1500:
        result = x * 3.5
    elif x < 2000:
        result = x * 3
    elif x < 3000:
        result = x * 2.5
    elif x < 4000:
        result = x * 2
    else:
        result = x * 1.5

    return round(max(result, 590))


def parse_dimensions(dim_str: str) -> tuple[int, int, int]:
    """Парсит строку с габаритами (ВxДxШ в см) и возвращает их в мм."""
    try:
        dims = re.findall(r'(\d+\.?\d*)', dim_str)
        if len(dims) == 3:
            height_cm, length_cm, width_cm = map(float, dims)
            return round(width_cm * 10), round(height_cm * 10), round(length_cm * 10)
    except (ValueError, IndexError):
        pass
    return 0, 0, 0


def parse_stock_value(stock_str: str) -> int:
    """Безопасно извлекает числовое значение из строки остатка, например, '12 шт.' или '+16526 шт.'."""
    if not isinstance(stock_str, str):
        return 0
    match = re.search(r'(\d+)', stock_str)
    return int(match.group(1)) if match else 0


def create_df_by_dict(data_dict):
    """
    Преобразует словарь с данными о товарах в три DataFrame:
    основной, с нежелательными брендами и с детализированными остатками.
    """
    all_rows = []
    for key, value in data_dict.items():
        characteristics = value.get("characteristics", {})
        current_stocks = value.get("stocks", {})

        country = characteristics.get("Производитель", "N/A")
        weight_str = characteristics.get("Вес с упаковкой", "0")
        if 'кг' in weight_str.lower():
            weight_g = int(float(re.sub(r'[^0-9,.]', '', weight_str).replace(',', '.')) * 1000)
        else:
            weight_g = int(re.sub(r'[^0-9]', '', weight_str) or 0)

        dimensions_str = characteristics.get("Размер в упаковке", "0x0x0")
        width_mm, height_mm, length_mm = parse_dimensions(dimensions_str)

        image_urls = value.get("image_urls", [])
        img_url1 = image_urls[0] if image_urls else "-"
        img_url2 = ", ".join(image_urls[1:]) if len(image_urls) > 1 else "-"

        row = {
            "ArtNumber": value.get("code", key.replace("goods_", "")), "Название": value.get("name", ""),
            "Цена Европы": value.get("price", 0), "Описание": value.get("description", ""),
            "Ссылка на главное фото товара": img_url1, "Ссылки на другие фото товара": img_url2,
            "art_url": value.get("product_url", ""), "Бренд": value.get("brand", "NoName"),
            "Характеристики": str(characteristics), "Страна": country, "Вес": weight_g,
            "Ширина, мм": width_mm, "Высота, мм": height_mm, "Длина, мм": length_mm,
            "raw_stocks": current_stocks
        }
        all_rows.append(row)

    if not all_rows:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    df = pd.DataFrame(all_rows)
    excluded_brands = read_bad_brand()
    df["Бренд_нижний_регистр"] = df["Бренд"].str.lower().str.strip()
    df_filtered = df[~df["Бренд_нижний_регистр"].isin(excluded_brands)].copy()
    df_excluded = df[df["Бренд_нижний_регистр"].isin(excluded_brands)].copy()

    if not df_excluded.empty:
        df_excluded["Артикул"] = df_excluded["ArtNumber"].apply(lambda art: f'goods_{art}')
        df_excluded = df_excluded[["Артикул", "Название", "Бренд", "art_url"]]
    else:
        df_excluded = pd.DataFrame(columns=["Артикул", "Название", "Бренд", "art_url"])

    df_filtered["Артикул"] = df_filtered["ArtNumber"].apply(lambda art: f'goods_{art}')
    df_filtered['Цена для OZON'] = df_filtered['Цена Европы'].apply(transform_price)
    df_filtered['Цена до скидки'] = df_filtered['Цена для OZON'].apply(lambda x: int(round(x * 1.3)))
    df_filtered["НДС"] = "Не облагается"

    desired_order = [
        'Артикул', 'Название', 'Цена для OZON', 'Цена до скидки', 'НДС', 'Цена Европы',
        'Вес', 'Ширина, мм', 'Высота, мм', 'Длина, мм', 'Ссылка на главное фото товара',
        'Ссылки на другие фото товара', 'Бренд', 'ArtNumber', 'Описание', 'Страна',
        'Характеристики', 'art_url'
    ]
    result_df = df_filtered[desired_order]

    # --- Подготовка листа "Остатки" ---
    stocks_rows = []

    TARGET_STORE_1 = "г. Брянск, ул. Красноармейская, 93Б, ТЦ Профиль"
    TARGET_STORE_2 = "г. Брянск, ул. Советская, д. 99"
    SUM_COLUMN_NAME = "Красноармейская+Советская"
    REMOTE_WAREHOUSE_COLUMN_NAME = "Удаленный склад"

    LOCAL_STORES = {
        TARGET_STORE_1,
        TARGET_STORE_2,
        "г. Брянск, ул. 3-го Интернационала, 13",
        "Наличие на складе в Брянске"
    }

    for _, product in df_filtered.iterrows():
        current_stocks = product["raw_stocks"]

        stock_row = {
            "Артикул": product["Артикул"],
            "Название": product["Название"]
        }

        stock1 = parse_stock_value(current_stocks.get(TARGET_STORE_1, "0"))
        stock2 = parse_stock_value(current_stocks.get(TARGET_STORE_2, "0"))
        stock_row[SUM_COLUMN_NAME] = stock1 + stock2

        # Собираем остатки со всех удаленных складов в список
        remote_stocks_list = [
            parse_stock_value(stock_value)
            for store_name, stock_value in current_stocks.items()
            if store_name not in LOCAL_STORES
        ]

        # Находим наименьшее значение, если удаленные склады есть, иначе 0
        stock_row[REMOTE_WAREHOUSE_COLUMN_NAME] = min(remote_stocks_list) if remote_stocks_list else 0

        stock_row["Наличие на складе в Брянске"] = parse_stock_value(
            current_stocks.get("Наличие на складе в Брянске", "0")
        )
        stock_row["г. Брянск, ул. 3-го Интернационала, 13"] = parse_stock_value(
            current_stocks.get("г. Брянск, ул. 3-го Интернационала, 13", "0")
        )
        stock_row[TARGET_STORE_1] = stock1
        stock_row[TARGET_STORE_2] = stock2

        stocks_rows.append(stock_row)

    df_stocks = pd.DataFrame(stocks_rows)

    final_stock_columns = [
        'Артикул', 'Название', SUM_COLUMN_NAME, 'Наличие на складе в Брянске',
        REMOTE_WAREHOUSE_COLUMN_NAME, 'г. Брянск, ул. 3-го Интернационала, 13',
        TARGET_STORE_1, TARGET_STORE_2
    ]

    if not df_stocks.empty:
        df_stocks = df_stocks[final_stock_columns]
    else:
        df_stocks = pd.DataFrame(columns=final_stock_columns)

    return result_df, df_excluded, df_stocks


def create_xls(df_res, df_excluded, df_stocks, file_name):
    """
    Сохраняет DataFrame'ы в Excel-файл с тремя листами и форматированием.
    """
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
        # Лист "OZON"
        if not df_res.empty:
            df_res.to_excel(writer, sheet_name='OZON', index=False, na_rep='NaN')
            worksheet_ozon = writer.sheets['OZON']
            for i, column in enumerate(df_res.columns, 1):
                column_letter = get_column_letter(i)
                column_width = min(max(df_res[column].astype(str).map(len).max(), len(column)) + 2, 50)
                worksheet_ozon.column_dimensions[column_letter].width = column_width
            worksheet_ozon.freeze_panes = 'A2'

        # Лист "Остатки"
        if not df_stocks.empty:
            df_stocks.to_excel(writer, sheet_name='Остатки', index=False, na_rep='NaN')
            worksheet_stocks = writer.sheets['Остатки']
            for i, column in enumerate(df_stocks.columns, 1):
                column_letter = get_column_letter(i)
                # Для длинного названия суммарного столбца делаем исключение
                if column == "Красноармейская+Советская":
                    column_width = 30
                else:
                    column_width = min(max(df_stocks[column].astype(str).map(len).max(), len(column)) + 2, 40)
                worksheet_stocks.column_dimensions[column_letter].width = column_width
            worksheet_stocks.freeze_panes = 'A2'

        # Лист "Нежелательный бренд"
        if not df_excluded.empty:
            df_excluded.to_excel(writer, sheet_name='Нежелательный бренд', index=False, na_rep='NaN')
            worksheet_excluded = writer.sheets['Нежелательный бренд']
            for i, column in enumerate(df_excluded.columns, 1):
                column_letter = get_column_letter(i)
                column_width = min(max(df_excluded[column].astype(str).map(len).max(), len(column)) + 2, 50)
                worksheet_excluded.column_dimensions[column_letter].width = column_width
            worksheet_excluded.freeze_panes = 'A2'


if __name__ == '__main__':
    data_json = read_json()
    if data_json:
        df_res, df_excluded, df_stocks = create_df_by_dict(data_dict=data_json)
        create_xls(df_res, df_excluded, df_stocks, file_name=RESULT_FILE_NAME)
        print(f"Excel-файл '{RESULT_FILE_NAME}' успешно создан.")
