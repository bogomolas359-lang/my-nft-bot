import os
import aiohttp
from database import DB_PATH

# Токен из переменной окружения (безопасно!)
TRYBIT_TOKEN = os.environ.get("TRYBIT_TOKEN", "eyJ0eXAi1iJKV1QiLCJhbGciOiJIAcI1NiJ9.eyJpZCI6MTMsImV4cCI6MTYzMTc4NjQyNn0.HQavV3z8dFnk56bX3MSY5X9lR6qVa9YhAoeTEH")
TRYBIT_BASE_URL = "https://api.trybit.com/v2"

HEADERS = {
    "Authorization": f"Token {TRYBIT_TOKEN}",
    "Content-Type": "application/json"
}


async def create_invoice(amount: float, currency: str, deal_number: str, description: str = "NFT Deal"):
    """Создаёт инвойс для оплаты сделки."""
    url = f"{TRYBIT_BASE_URL}/invoice/create"
    
    payload = {
        "amount": amount,
        "currency": currency,
        "order_id": deal_number,
        "description": description
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=HEADERS, json=payload, timeout=30) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                text = await response.text()
                print(f"[TryBit] Ошибка создания инвойса: {response.status} — {text}")
                return None


async def check_invoice_status(invoice_id: str):
    """Проверяет статус инвойса."""
    url = f"{TRYBIT_BASE_URL}/invoice/status"
    params = {"invoice_id": invoice_id}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS, params=params, timeout=30) as response:
            if response.status == 200:
                return await response.json()
            return None