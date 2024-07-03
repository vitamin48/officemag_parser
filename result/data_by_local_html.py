from bs4 import BeautifulSoup

url = 'https://www.officemag.ru/catalog/goods/454239/'

with open("page_content_art.html", "r", encoding='utf-8') as file:
    file_content = file.read()
soup = BeautifulSoup(file_content, "html.parser")
"характеристики"
# Находим блок "Подробнее о товаре"
details_section = soup.find('div', class_='TabsContentSpoiler__content')
characteristics_dict = {}
if details_section:
    # Находим все элементы списка характеристик
    characteristics_list = details_section.find('ul', class_='infoFeatures')
    if characteristics_list:
        # Извлекаем текст каждого элемента списка
        for item in characteristics_list.find_all('li'):
            text = item.get_text(strip=True)
            # Ищем разделители "-" и ":"
            if "—" in text:
                key, value = text.split("—", 1)
            elif ":" in text:
                key, value = text.split(":", 1)
            else:
                # Если разделителей нет, пропускаем элемент
                continue

            characteristics_dict[key.strip()] = value.strip()
"остатки"
table = soup.find('table', class_='AvailabilityList')
data_stocks = {}
rows = table.find_all('tr', class_='AvailabilityItem')
for row in rows:
    # Извлекаем данные из первой ячейки (название магазина)
    store_cell = row.find('td', class_='AvailabilityBox')
    store_name = store_cell.find('span', class_='AvailabilityLabel').text.strip()

    # Извлекаем данные из второй ячейки (наличие товара)
    availability_cell = row.find('td', class_='AvailabilityBox AvailabilityBox--green')
    availability = availability_cell.text.strip()

    # Записываем данные в словарь
    data_stocks[store_name] = availability
# Ищем остатки на складах
warehouse_stocks = ''
print()
