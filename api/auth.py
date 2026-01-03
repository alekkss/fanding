import hmac
import hashlib
import os
from dotenv import load_dotenv
import urllib.parse

# def create_signature(secret, params):
#     """
#     Создает подпись для запроса к Bybit API.
#     :param secret: Секретный ключ API.
#     :param params: Параметры запроса в виде словаря.
#     :return: Строка подписи.
#     """
#     # 1. Сортируем параметры в алфавитном порядке
#     sorted_params = dict(sorted(params.items()))

#     # 2. Создаем строку для подписи в формате "key1=value1&key2=value2&..."
#     query_string = '&'.join(f"{key}={value}" for key, value in sorted_params.items())

#     # 3. Создаем HMAC-SHA256 подпись
#     signature = hmac.new(
#         secret.encode('utf-8'),
#         query_string.encode('utf-8'),
#         hashlib.sha256
#     ).hexdigest()

#     return signature
# Загрузка переменных окружения
load_dotenv()

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")

# Проверка загрузки
if not API_KEY or not API_SECRET:
    raise ValueError("API ключи не найдены. Проверьте файл .env!")

# Функция для получения API_KEY и API_SECRET
def get_api_key():
    return API_KEY

def get_api_secret():
    return API_SECRET

# Создание подписи для запроса
def create_signature(secret, params):
    """
    Создает подпись для запроса к Bybit API.
    :param secret: Секретный ключ API.
    :param params: Параметры запроса в виде словаря.
    :return: Строка подписи.
    """
    # 1. Сортируем параметры в алфавитном порядке
    sorted_params = dict(sorted(params.items()))

    # 2. Создаем строку для подписи в формате "key1=value1&key2=value2&..."
    query_string = '&'.join(f"{key}={value}" for key, value in sorted_params.items())

    # 3. Создаем HMAC-SHA256 подпись
    signature = hmac.new(
        secret.encode('utf-8'),
        query_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return signature