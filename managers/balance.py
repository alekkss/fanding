import requests
import pandas as pd
from utils.utils import get_corrected_timestamp  # Импорт функции для работы с временными метками
from api.auth import (
    get_api_key,
    get_api_secret,
    create_signature  # Импорт функций для работы с API
)


# Константы для API Bybit
# Базовые параметры API
BASE_URL = "https://api.bybit.com"
BALANCE_ENDPOINT = "/v5/account/wallet-balance"

def get_wallet_balance():
    """
    Получает баланс для Unified Account (Bybit API v5).
    """
    # Получаем текущую временную метку
    timestamp = get_corrected_timestamp()

    # Формируем параметры для запроса
    params = {
        "api_key": get_api_key(),  # API Key
        "timestamp": str(timestamp),
        "accountType": "UNIFIED",  # Поддерживается только 'UNIFIED'
        "recvWindow": "5000"       # Время ожидания
    }

    # Создаём подпись
    sign = create_signature(get_api_secret(), params)
    params["sign"] = sign

    try:
        # Выполняем запрос
        url = f"{BASE_URL}{BALANCE_ENDPOINT}"
        response = requests.get(url, params=params)
        data = response.json()

        if data.get("retCode") == 0:
            print("✅ Баланс успешно получен:")
            return data.get("result")
        else:
            print(f"⚠️ Ошибка при получении баланса: {data.get('retMsg')}")
            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def save_balance_to_excel(balance_data, filename="wallet_balance.xlsx"):
    """
    Сохраняет данные в Excel на два листа:
      1) 'Общая сводка' — верхний уровень (totalEquity, totalMarginBalance и т.д.)
      2) 'Монеты' — детальная информация по каждой монете.
    """
    if not balance_data:
        print("Пустые данные — ничего сохранять.")
        return

    # Достаём список из balance_data["list"]
    data_list = balance_data.get("list", [])
    if not isinstance(data_list, list) or len(data_list) == 0:
        print("В 'result' нет поля 'list' или оно пустое.")
        return

    # Обычно в 'list' лежит 1 объект, содержащий нужную нам информацию
    first_item = data_list[0]

    # 1) Формируем «Общую сводку» (верхний уровень)
    # Выберите нужные ключи (можете дописать или убрать лишние)
    top_level_keys = [
        "accountType",
        "totalEquity",
        "totalMarginBalance",
        "totalAvailableBalance",
        "totalWalletBalance",
        "totalInitialMargin",
        "totalMaintenanceMargin",
        "totalPerpUPL",
        "accountIMRate",
        "accountMMRate",
        "accountLTV",
    ]

    top_data = {}
    for key in top_level_keys:
        # Получаем значение из первого элемента
        top_data[key] = first_item.get(key)

    # Создаём DataFrame из одного словаря (будет одна строка)
    df_overview = pd.DataFrame([top_data])

    # 2) Формируем лист с монетами
    # Под полем "coin" обычно массив вида:
    # [
    #   {"coin": "BTC", "equity": "0.00093219", ...},
    #   {"coin": "XRP", "equity": "303.71267182", ...},
    #   ...
    # ]
    coins_data = first_item.get("coin", [])

    if isinstance(coins_data, list) and len(coins_data) > 0 and isinstance(coins_data[0], dict):
        df_coins = pd.DataFrame(coins_data)
    else:
        # Пустой или неверный формат
        df_coins = pd.DataFrame()

    # 3) Сохраняем оба листа в один Excel-файл
    with pd.ExcelWriter(filename) as writer:
        df_overview.to_excel(writer, sheet_name="Общая сводка", index=False)
        df_coins.to_excel(writer, sheet_name="Монеты", index=False)

    print(f"✅ Данные успешно сохранены в {filename}")
def get_coin_balance(symbol: str) -> float:
    """Получает баланс конкретной монеты"""
    balance_data = get_wallet_balance()
    
    if not balance_data:
        return 0.0
    
    data_list = balance_data.get("list", [])
    if data_list:
        coins = data_list[0].get("coin", [])
        for coin_data in coins:
            if coin_data.get("coin") == symbol:
                available = coin_data.get("availableToWithdraw", "0")
                wallet_bal = coin_data.get("walletBalance", "0")
                
                if available and available != "":
                    return float(available)
                elif wallet_bal and wallet_bal != "":
                    return float(wallet_bal)
    return 0.0

if __name__ == "__main__":
    balance = get_wallet_balance()   # Здесь вернётся data["result"] 
    if balance:
        save_balance_to_excel(balance)
    else:
        print("Не удалось получить баланс.")