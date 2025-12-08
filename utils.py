import time
import requests

def get_server_time():
    try:
        response = requests.get("https://api.bybit.com/v5/market/time")
        response.raise_for_status()  # Проверка на ошибки запроса
        return response.json().get("time")
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении времени: {e}")
        return None

def get_corrected_timestamp():
    # Получаем серверное время и корректируем локальное время
    server_time = get_server_time()
    if server_time is None:
        return None  # В случае ошибки при получении времени, возвращаем None

    local_time = int(time.time() * 1000)
    time_diff = server_time - local_time
    timestamp = local_time + time_diff  # Корректируем локальное время с учетом разницы

    return timestamp