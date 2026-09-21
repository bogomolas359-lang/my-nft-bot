import os
import aiohttp
from typing import Optional, Dict, Any

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
            "time_to_pay": {"hours": time_to_pay_hours, "minutes": 0}
        }
    }
    if cryptocurrency:
        payload["add_fields"]["cryptocurrency"] = cryptocurrency

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=HEADERS, json=payload, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        return data.get("result")
                    print(f"[TryBit] ❌ Ошибка API: {data}")
                    return None
                text = await response.text()
                print(f"[TryBit] ❌ HTTP {response.status}: {text}")
                return None
    except Exception as e:
        print(f"[TryBit] ❌ Ошибка запроса: {e}")
        return None


def get_payment_link(invoice_result: Dict[str, Any]) -> Optional[str]:
    return invoice_result.get("link")


def get_payment_address(invoice_result: Dict[str, Any]) -> Optional[str]:
    return invoice_result.get("address")


def get_invoice_uuid(invoice_result: Dict[str, Any]) -> Optional[str]:
    return invoice_result.get("uuid")