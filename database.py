import aiosqlite
import os
from datetime import datetime
import random

# Создаём папку data для сохранения БД между рестартами
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "bot.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                language TEXT DEFAULT 'ru',
                card_number TEXT,
                stars_username TEXT,
                usdt_wallet TEXT,
                ton_wallet TEXT,
                successful_deals INTEGER DEFAULT 0,
                is_admin INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                deal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                deal_number TEXT UNIQUE,
                seller_id INTEGER,
                seller_username TEXT,
                buyer_id INTEGER,
                buyer_username TEXT,
                gift_link TEXT,
                amount REAL,
                currency TEXT,
                payment_details TEXT,
                status TEXT DEFAULT 'waiting_for_buyer',
                created_at TEXT
            )
        """)
        await db.commit()
        # Ensure main admin exists
        async with db.execute("SELECT * FROM users WHERE user_id=5461944251") as cur:
            if not await cur.fetchone():
    await db.execute("""
        INSERT INTO users (user_id, username, is_admin, successful_deals)
        VALUES (5461944251, 'MainAdmin', 1, 32)
    """)
    await db.commit()

# Обновляем успешные сделки у ВСЕХ админов до 32
await db.execute("UPDATE users SET successful_deals=32 WHERE is_admin=1")
await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur2:
                    row = await cur2.fetchone()
            return dict(row)

async def update_user(user_id, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = ", ".join(f"{k}=?" for k in kwargs.keys())
        values = list(kwargs.values()) + [user_id]
        await db.execute(f"UPDATE users SET {fields} WHERE user_id=?", values)
        await db.commit()

async def create_deal(seller_id, seller_username, gift_link, amount, currency, payment_details):
    deal_number = f"ALX{random.randint(100000, 999999)}"
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO deals (deal_number, seller_id, seller_username, gift_link, amount, currency, payment_details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (deal_number, seller_id, seller_username, gift_link, amount, currency, payment_details, now))
        await db.commit()
    return deal_number

async def get_deal_by_number(deal_number):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM deals WHERE deal_number=?", (deal_number,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_deal_by_id(deal_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM deals WHERE rowid=?", (deal_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def get_all_deals():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT rowid, * FROM deals ORDER BY rowid DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

async def join_deal(deal_number, buyer_id, buyer_username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE deals SET buyer_id=?, buyer_username=?, status='buyer_joined'
            WHERE deal_number=?
        """, (buyer_id, buyer_username, deal_number))
        await db.commit()

async def confirm_payment(deal_number):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE deals SET status='paid' WHERE deal_number=?
        """, (deal_number,))
        await db.commit()

async def complete_deal(deal_number):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE deals SET status='completed' WHERE deal_number=?
        """, (deal_number,))
        await db.commit()

async def add_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT * FROM users WHERE user_id=?", (user_id,)) as cur:
            if not await cur.fetchone():
                await db.execute("INSERT INTO users (user_id, is_admin, successful_deals) VALUES (?, 1, 32)", (user_id,))
            else:
                await db.execute("UPDATE users SET is_admin=1, successful_deals=32 WHERE user_id=?", (user_id,))
        await db.commit()

async def remove_admin(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_admin=0 WHERE user_id=?", (user_id,))
        await db.commit()

async def get_admins():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_admin=1") as cur:
            return [dict(r) for r in await cur.fetchall()]