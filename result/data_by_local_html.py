from bs4 import BeautifulSoup

url = 'https://www.officemag.ru/catalog/goods/454239/'

with open("page_content_art.html", "r", encoding='utf-8') as file:
    file_content = file.read()
soup = BeautifulSoup(file_content, "html.parser")
"характеристики"
# Находим блок "Подробнее о товаре"
details_section = soup.find('div', class_='TabsContentSpoiler__content')
characteristics_dict = {}
characteristics_text_list = []
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
            characteristics_text_list.append(text)
result_characteristics_text = " ".join(characteristics_text_list)
"остатки"
table = soup.find('table', class_='AvailabilityList')
div_stocks = soup.find('div', class_='tabsContent js-tabsContent js-tabsContentMobile')
rows = div_stocks.find_all('tr', class_='AvailabilityItem')
data_stocks = {}
for row in rows:
    store_cell = row.find('td', class_='AvailabilityBox')
    store_name = store_cell.find('span', class_='AvailabilityLabel').text.strip()
    # Извлекаем данные из второй ячейки (наличие товара)
    availability_cell = row.find('td', class_='AvailabilityBox AvailabilityBox--green')
    if availability_cell:
        availability = availability_cell.text.strip()
    else:
        availability = 0
    # Записываем данные в словарь
    data_stocks[store_name] = availability
"Описание"
description = (soup.find('div', class_='infoDescription').text.replace('Описание', '')
               .replace('\n\n', ' ')).replace('\n', ' ').strip()
# Добавляем к описанию характеристики
description = description + ' ' + result_characteristics_text
"Бренд"
brand = soup.find('span', class_='ProductBrand__name').text.strip()
"Изображения"
images_soup = soup.find('ul', class_='ProductPhotoThumbs').find_all('a', class_='ProductPhotoThumb__link')
image_urls = [link['href'] for link in images_soup]
"Код (Артикул)"
code = url.split('/')[-2]
"Название"
name = soup.find('div', class_='ProductHead__name').text.strip()
"Цена"
# price = soup.find('span', class_='Price__count').text.strip()
price_soup = soup.find('div', class_='order')
price = price_soup.find('div', class_='Product__price js-itemPropToRemove js-detailCardGoods')
print()
