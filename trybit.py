import os
import aiohttp
import asyncio
from typing import Optional, Dict, Any

# Конфигурация из переменных окружения
TRYBIT_TOKEN = os.environ.get("TRYBIT_TOKEN", "")
TRYBIT_SHOP_ID = os.environ.get("TRYBIT_SHOP_ID", "")
TRYBIT_BASE_URL = "https://api.trybit.com/v2"

HEADERS = {
    "Authorization": f"Token {TRYBIT_TOKEN}",
    "Content-Type": "application/json"
}


async def create_invoice(
    amount: float,
    currency: str,
    order_id: str,
    cryptocurrency: Optional[str] = None,
    time_to_pay_hours: int = 24
) -> Optional[Dict[str, Any]]:
    """
    Создаёт инвойс в TryBit для оплаты сделки.
    
    Args:
        amount: Сумма платежа в USD
        currency: Фиатная валюта (USD, RUB, EUR и т.д.)
        order_id: Номер сделки (ALX123456)
        cryptocurrency: Конкретная крипта для оплаты (USDT_TRC20, TON и т.д.)
        time_to_pay_hours: Время жизни счёта в часах
    
    Returns:
        dict с данными инвойса или None при ошибке
    """
    if not TRYBIT_TOKEN or not TRYBIT_SHOP_ID:
        print("[TryBit] ❌ Не заданы TRYBIT_TOKEN или TRYBIT_SHOP_ID")
        return None
    
    url = f"{TRYBIT_BASE_URL}/invoice/create"
    
    payload = {
        "amount": amount,
        "currency": currency,
        "shop_id": TRYBIT_SHOP_ID,
        "order_id": order_id,
        "add_fields": {
            "time_to_pay": {
                "hours": time_to_pay_hours,
                "minutes": 0
            }
        }
    }
    
    # Если указана конкретная крипта — добавляем её
    if cryptocurrency:
        payload["add_fields"]["cryptocurrency"] = cryptocurrency
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=HEADERS, json=payload, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        return data.get("result")
                    else:
                        print(f"[TryBit] ❌ Ошибка API: {data}")
                        return None
                else:
                    text = await response.text()
                    print(f"[TryBit] ❌ HTTP {response.status}: {text}")
                    return None
    except Exception as e:
        print(f"[TryBit] ❌ Ошибка запроса: {e}")
        return None


async def check_invoice_status(uuid: str) -> Optional[str]:
    """
    Проверяет статус инвойса по UUID.
    
    Returns:
        Статус: 'created', 'paid', 'partial', 'overpaid', 'canceled' или None
    """
    if not TRYBIT_TOKEN:
        return None
    
    # Предположительно endpoint для проверки статуса
    url = f"{TRYBIT_BASE_URL}/invoice/status"
    params = {"uuid": uuid}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        return data.get("result", {}).get("status")
                return None
    except Exception as e:
        print(f"[TryBit] ❌ Ошибка проверки статуса: {e}")
        return None


def get_payment_link(invoice_result: Dict[str, Any]) -> Optional[str]:
    """Извлекает ссылку на оплату из результата создания инвойса."""
    return invoice_result.get("link")


def get_payment_address(invoice_result: Dict[str, Any]) -> Optional[str]:
    """Извлекает адрес для оплаты (если криптовалюта предвыбрана)."""
    return invoice_result.get("address")


def get_invoice_uuid(invoice_result: Dict[str, Any]) -> Optional[str]:
    """Извлекает UUID инвойса."""
    return invoice_result.get("uuid")