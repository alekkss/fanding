# -*- coding: utf-8 -*-

"""Исполнение ордеров спот и фьючерс"""

import logging
from decimal import Decimal, ROUND_DOWN
from api_client import BybitAPIClient
from config import TRADE_AMOUNT_USD

logger = logging.getLogger(__name__)

class OrderExecutor:
    TRADE_AMOUNT_USD = TRADE_AMOUNT_USD

    @staticmethod
    def get_instrument_info(symbol: str, category: str) -> dict:
        data = BybitAPIClient.get("/market/instruments-info", {
            "category": category,
            "symbol": f"{symbol}USDT"
        })
        try:
            instrument = data["result"]["list"][0]
            lot_size = instrument.get("lotSizeFilter", {})
            if category == "spot":
                return {
                    'basePrecision': lot_size.get('basePrecision', '0.01'),
                    'qtyStep': lot_size.get('basePrecision', '0.01')
                }
            else:
                return {
                    'qtyStep': lot_size.get('qtyStep', '0.001'),
                    'minOrderQty': lot_size.get('minOrderQty', '0.001'),
                }
        except Exception as e:
            logger.error(f"Ошибка получения информации об инструменте {symbol}: {e}")
            if category == "spot":
                return {'basePrecision': '0.01', 'qtyStep': '0.01'}
            else:
                return {'qtyStep': '0.001', 'minOrderQty': '0.001'}

    @staticmethod
    def round_to_step(value: float, step: str, rounding_mode=ROUND_DOWN) -> str:
        value_dec = Decimal(str(value))
        step_dec = Decimal(step)
        rounded = (value_dec / step_dec).quantize(Decimal('1'), rounding=rounding_mode) * step_dec
        # ✅ ИСПРАВЛЕНО: используем str() вместо f-string с rstrip
        result = str(rounded)
        return result

    @staticmethod
    def calculate_futures_amount(symbol: str, price: float, target_usdt: float) -> float:
        info = OrderExecutor.get_instrument_info(symbol, "linear")
        minOrderQty = float(info.get('minOrderQty', '0.001'))
        min_order_value = minOrderQty * price
        if min_order_value > target_usdt:
            logger.warning(f"Минимальная стоимость для {symbol}: {min_order_value:.2f} USDT > {target_usdt} USDT")
            logger.info(f"Будет использована сумма: {min_order_value:.2f} USDT")
            return min_order_value
        return target_usdt

    @staticmethod
    def place_spot_order(symbol: str, side: str, usdt_amount: float) -> dict:
        """
        Размещает спот ордер с полной проверкой ответа
        Возвращает: {"success": bool, "order_id": str, "qty": float, "price": float, "error": str}
        """
        usdt_amount_rounded = round(usdt_amount, 2)
        data = {
            "category": "spot",
            "symbol": f"{symbol}USDT",
            "side": side,
            "orderType": "Market",
            "qty": str(usdt_amount_rounded),
            "marketUnit": "quoteCoin",
            "timeInForce": "IOC",
            "isLeverage": 0
        }
        
        logger.info(f"[SPOT] Размещаю {side} {symbol} на {usdt_amount_rounded} USDT")
        
        response = BybitAPIClient.post("/order/create", data)
        
        ret_code = response.get('retCode')
        ret_msg = response.get('retMsg', 'Unknown error')
        
        if ret_code == 0:
            result = response.get('result', {})
            order_id = result.get('orderId', 'N/A')
            
            logger.info(f"✅ [SPOT SUCCESS] {side} {symbol} | {usdt_amount_rounded} USDT | OrderID: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "usdt_amount": usdt_amount_rounded,
                "symbol": symbol,
                "side": side,
                "error": None
            }
        else:
            logger.error(f"❌ [SPOT FAILED] {side} {symbol} | Code: {ret_code} | Msg: {ret_msg}")
            logger.error(f"   Full response: {response}")
            
            return {
                "success": False,
                "order_id": None,
                "usdt_amount": usdt_amount_rounded,
                "symbol": symbol,
                "side": side,
                "error": f"Code {ret_code}: {ret_msg}"
            }

    @staticmethod
    def place_futures_order(symbol: str, side: str, price: float, usdt_amount: float) -> dict:
        """
        Размещает фьючерс ордер с полной проверкой ответа
        Возвращает: {"success": bool, "order_id": str, "qty": float, "price": float, "error": str}
        """
        info = OrderExecutor.get_instrument_info(symbol, "linear")
        qtyStep = info.get('qtyStep', '0.001')
        minOrderQty = float(info.get('minOrderQty', '0.001'))
        
        target_qty = usdt_amount / price
        qty_final = max(target_qty, minOrderQty)
        
        step_decimal = Decimal(qtyStep)
        qty_decimal = Decimal(str(qty_final))
        qty_rounded = (qty_decimal / step_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_decimal
        
        # ✅ ИСПРАВЛЕНО: используем str() вместо f-string с rstrip
        rounded_qty_str = str(qty_rounded)
        rounded_qty_float = float(qty_rounded)
        
        order_value = rounded_qty_float * price
        
        data = {
            "category": "linear",
            "symbol": f"{symbol}USDT",
            "side": side,
            "orderType": "Market",
            "qty": rounded_qty_str,
            "timeInForce": "IOC",
            "positionIdx": 0
        }
        
        logger.info(f"[FUTURES] Размещаю {side} qty={rounded_qty_float} {symbol} @ ~{price:.6f} (стоимость: {order_value:.2f} USDT)")
        
        response = BybitAPIClient.post("/order/create", data)
        
        ret_code = response.get('retCode')
        ret_msg = response.get('retMsg', 'Unknown error')
        
        if ret_code == 0:
            result = response.get('result', {})
            order_id = result.get('orderId', 'N/A')
            
            logger.info(f"✅ [FUTURES SUCCESS] {side} qty={rounded_qty_float} {symbol} | OrderID: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "qty": rounded_qty_float,
                "price": price,
                "symbol": symbol,
                "side": side,
                "error": None
            }
        else:
            logger.error(f"❌ [FUTURES FAILED] {side} {symbol} | Code: {ret_code} | Msg: {ret_msg}")
            logger.error(f"   Full response: {response}")
            
            return {
                "success": False,
                "order_id": None,
                "qty": rounded_qty_float,
                "symbol": symbol,
                "side": side,
                "error": f"Code {ret_code}: {ret_msg}"
            }

    @staticmethod
    def close_spot_position_qty(symbol: str, qty: float) -> dict:
        """
        Закрывает спот позицию с полной проверкой ответа
        Возвращает: {"success": bool, "order_id": str, "qty": float, "error": str}
        """
        if qty <= 0:
            error_msg = f"Недостаточно {symbol} для закрытия спота: qty={qty}"
            logger.error(error_msg)
            return {
                "success": False,
                "order_id": None,
                "qty": qty,
                "symbol": symbol,
                "error": error_msg
            }
        
        info = OrderExecutor.get_instrument_info(symbol, "spot")
        qtyStep = info.get('basePrecision', '0.01')
        
        qty_decimal = Decimal(str(qty))
        step_decimal = Decimal(qtyStep)
        qty_rounded = (qty_decimal / step_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_decimal
        
        # ✅ ИСПРАВЛЕНО: используем str() вместо f-string с rstrip
        qty_str = str(qty_rounded)
        qty_float = float(qty_rounded)
        
        logger.info(f"[SPOT CLOSE] Рассчитанное qty: {qty_float} {symbol}")
        
        data = {
            "category": "spot",
            "symbol": f"{symbol}USDT",
            "side": "Sell",
            "orderType": "Market",
            "qty": qty_str,
            "timeInForce": "IOC"
        }
        
        logger.info(f"[SPOT CLOSE] Размещаю Sell {qty_str} {symbol}")
        
        response = BybitAPIClient.post("/order/create", data)
        
        ret_code = response.get('retCode')
        ret_msg = response.get('retMsg', 'Unknown error')
        
        if ret_code == 0:
            result = response.get('result', {})
            order_id = result.get('orderId', 'N/A')
            
            logger.info(f"✅ [SPOT CLOSE SUCCESS] Sell {qty_str} {symbol} | OrderID: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "qty": qty_float,
                "symbol": symbol,
                "error": None
            }
        else:
            logger.error(f"❌ [SPOT CLOSE FAILED] Sell {symbol} | Code: {ret_code} | Msg: {ret_msg}")
            logger.error(f"   Full response: {response}")
            
            return {
                "success": False,
                "order_id": None,
                "qty": qty_float,
                "symbol": symbol,
                "error": f"Code {ret_code}: {ret_msg}"
            }

    @staticmethod
    def close_futures_position(symbol: str, price: float, qty: float) -> dict:
        """
        Закрывает фьючерс позицию с полной проверкой ответа
        Возвращает: {"success": bool, "order_id": str, "qty": float, "error": str}
        """
        info = OrderExecutor.get_instrument_info(symbol, "linear")
        qtyStep = info.get('qtyStep', '0.001')
        
        qty_decimal = Decimal(str(qty))
        step_decimal = Decimal(qtyStep)
        qty_rounded = (qty_decimal / step_decimal).quantize(Decimal('1'), rounding=ROUND_DOWN) * step_decimal
        
        # ✅ ИСПРАВЛЕНО: используем str() вместо f-string с rstrip
        rounded_qty_str = str(qty_rounded)
        rounded_qty_float = float(qty_rounded)
        
        logger.info(f"[FUTURES CLOSE] Рассчитанное qty: {qty:.4f} → {rounded_qty_float} {symbol} (шаг: {qtyStep})")
        
        data = {
            "category": "linear",
            "symbol": f"{symbol}USDT",
            "side": "Buy",
            "orderType": "Market",
            "qty": rounded_qty_str,
            "timeInForce": "IOC",
            "positionIdx": 0,
            "reduceOnly": True
        }
        
        logger.info(f"[FUTURES CLOSE] Размещаю Buy {rounded_qty_str} {symbol} @ ~{price}")
        
        response = BybitAPIClient.post("/order/create", data)
        
        ret_code = response.get('retCode')
        ret_msg = response.get('retMsg', 'Unknown error')
        
        if ret_code == 0:
            result = response.get('result', {})
            order_id = result.get('orderId', 'N/A')
            
            logger.info(f"✅ [FUTURES CLOSE SUCCESS] Buy {rounded_qty_str} {symbol} | OrderID: {order_id}")
            
            return {
                "success": True,
                "order_id": order_id,
                "qty": rounded_qty_float,
                "symbol": symbol,
                "error": None
            }
        else:
            logger.error(f"❌ [FUTURES CLOSE FAILED] Buy {symbol} | Code: {ret_code} | Msg: {ret_msg}")
            logger.error(f"   Full response: {response}")
            
            return {
                "success": False,
                "order_id": None,
                "qty": rounded_qty_float,
                "symbol": symbol,
                "error": f"Code {ret_code}: {ret_msg}"
            }
