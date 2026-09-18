import aiosqlite
import os
from datetime import datetime
import random
from datetime import datetime, timedelta

HOLD_DAYS = 3  # Срок холда средств (дни)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "bot.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("""
            CREATE TABLE IF NOT EXISTS balance_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount REAL,
                currency TEXT,
                type TEXT,
                deal_number TEXT,
                created_at TEXT,
                available_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS withdrawals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                amount REAL,
                currency TEXT,
                details TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await db.commit()

        async with db.execute("SELECT * FROM users WHERE user_id=5461944251") as cur:
            if not await cur.fetchone():
                await db.execute("""
                    INSERT INTO users (user_id, username, is_admin, successful_deals)
                    VALUES (5461944251, 'MainAdmin', 1, 32)
                """)
                await db.commit()

        # Обновляем успешные сделки у всех админов до 32
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
                await db.execute(
                    "INSERT INTO users (user_id, is_admin, successful_deals) VALUES (?, 1, 32)",
                    (user_id,)
                )
            else:
                await db.execute(
                    "UPDATE users SET is_admin=1, successful_deals=32 WHERE user_id=?",
                    (user_id,)
                )
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
            # ================= ВНУТРЕННИЙ БАЛАНС =================

async def add_balance(user_id, amount, currency, deal_number):
    """Зачисляет средства на баланс с холдом 3 дня."""
    now = datetime.now()
    available_at = (now + timedelta(days=HOLD_DAYS)).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO balance_transactions (user_id, amount, currency, type, deal_number, created_at, available_at)
            VALUES (?, ?, ?, 'deposit', ?, ?, ?)
        """, (user_id, amount, currency, deal_number, now.isoformat(), available_at))
        await db.commit()


async def get_balance_info(user_id):
    """Возвращает (инфо по валютам, дата ближайшей разморозки)."""
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT currency, SUM(amount) t FROM balance_transactions WHERE user_id=? AND type='deposit' GROUP BY currency",
            (user_id,)) as cur:
            deposits = {r["currency"]: r["t"] for r in await cur.fetchall()}
        async with db.execute(
            "SELECT currency, SUM(amount) t FROM balance_transactions WHERE user_id=? AND type='deposit' AND available_at<=? GROUP BY currency",
            (user_id, now)) as cur:
            matured = {r["currency"]: r["t"] for r in await cur.fetchall()}
        async with db.execute(
            "SELECT currency, SUM(amount) t FROM withdrawals WHERE user_id=? AND status IN ('pending','approved') GROUP BY currency",
            (user_id,)) as cur:
            reserved = {r["currency"]: r["t"] for r in await cur.fetchall()}
        async with db.execute(
            "SELECT MIN(available_at) m FROM balance_transactions WHERE user_id=? AND type='deposit' AND available_at>?",
            (user_id, now)) as cur:
            row = await cur.fetchone()
            hold_until = row["m"] if row else None

    info = {}
    for cur_code in deposits:
        res = reserved.get(cur_code, 0)
        total = deposits.get(cur_code, 0) - res
        avail = matured.get(cur_code, 0) - res
        info[cur_code] = {"total": max(total, 0), "available": max(avail, 0)}
    return info, hold_until


async def create_withdrawal(user_id, username, amount, currency, details):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("""
            INSERT INTO withdrawals (user_id, username, amount, currency, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, username, amount, currency, details, now))
        await db.commit()
        return cur.lastrowid


async def get_pending_withdrawals():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdrawals WHERE status='pending' ORDER BY id") as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_withdrawal(w_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM withdrawals WHERE id=?", (w_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_withdrawal_status(w_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE withdrawals SET status=? WHERE id=?", (status, w_id))
        await db.commit()