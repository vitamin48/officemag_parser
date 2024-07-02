"""
Скрипт считывает все ссылки на все каталоги магазина из https://www.officemag.ru/catalog/abc/.
На выходе текстовый файл со списком каталогов.
"""

import requests
from bs4 import BeautifulSoup

# URL страницы
ABC_CATALOG = "https://www.officemag.ru/catalog/abc/"


def save_html():
    response = requests.get(ABC_CATALOG)
    page_content = response.text
    # Сохранение содержимого страницы в файл
    with open("result\\page_content_catalogs.html", "w", encoding='utf-8') as file:
        file.write(page_content)


def get_soup_by_html(path_to_html):
    # Открытие и чтение содержимого файла
    with open(path_to_html, "r", encoding='utf-8') as file:
        file_content = file.read()
    soup = BeautifulSoup(file_content, "html.parser")
    return soup


def get_catalog_links(soup):
    catalog_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/catalog/") and href.count('/') == 3:  # проверяем, что ссылка ведет на каталог
            full_link = f"https://www.officemag.ru{href}"
            catalog_links.append(full_link)
    return catalog_links


def save_catalog_links(path_to_save, catalog_links):
    with open(path_to_save, "w") as file:
        for link in catalog_links:
            file.write(link + "\n")


if __name__ == '__main__':
    # save_html()
    soup = get_soup_by_html(path_to_html='result\\page_content_catalogs.html')
    catalog_links = get_catalog_links(soup)
    save_catalog_links(path_to_save='result\\catalogs.txt', catalog_links=catalog_links)
