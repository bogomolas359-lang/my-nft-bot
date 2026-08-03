from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
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
    """Отправка главного меню пользователю."""
    user = await db.get_user(user_id)
    lang = user["language"]
    is_admin = bool(user["is_admin"])
    text = t(lang, "welcome")
    kb = main_menu_kb(lang, is_admin)
    
    if edit and hasattr(message_or_call, "edit_text"):
        try:
            await message_or_call.edit_text(text, reply_markup=kb)
        except Exception:
            await message_or_call.message.answer(text, reply_markup=kb)
    else:
        await message_or_call.answer(text, reply_markup=kb)


# ================= СТАРТ =================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]

    # Deep-link: /start#DEALNUMBER
    args = message.text.split(" ", 1)
    if len(args) > 1 and args[1].startswith("#"):
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


@router.callback_query(F.data == "main_menu")
async def to_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_main_menu(call.message, call.from_user.id, edit=True)
    await call.answer()


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
    user = await db.get_user(message.from_user.id)
    lang = user["language"]

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
    else:  # USDT или TON
        await message.answer(t(lang, "enter_crypto_wallet"), reply_markup=back_cancel_kb(lang))

    await state.set_state(CreateDeal.waiting_for_details)


@router.message(CreateDeal.waiting_for_details)
async def process_details(message: Message, state: FSMContext, bot: Bot):
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

    # Уведомление продавцу
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

    # Уведомление всем админам
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
                f"🆔 Номер: #{d['deal_number']}\n"
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
        await call.answer("❌ Покупатель ещё не присоединился", show_alert=True)
        return

    if deal["status"] == "paid":
        await call.answer("✅ Сделка уже подтверждена", show_alert=True)
        return

    await db.confirm_payment(deal_number)

    # Уведомление продавцу
    try:
        await bot.send_message(
            deal["seller_id"],
            f"💸 Покупатель успешно произвел оплату!\n"
            f"🎁 Отправьте подарок: {deal['gift_link']}"
        )
    except Exception:
        pass

    # Уведомление покупателю с кнопкой подтверждения
    try:
        await bot.send_message(
            deal["buyer_id"],
            f"💸 Оплата подтверждена!\n"
            f"🎁 Подарок: {deal['gift_link']}\n\n"
            f"Когда получите подарок — нажмите кнопку ниже:",
            reply_markup=confirm_gift_kb("ru")
        )
    except Exception:
        pass

    await call.answer("✅ Оплата подтверждена!")
    await call.message.edit_text(f"✅ Сделка #{deal_number} подтверждена администратором.")


# ================= ПОКУПАТЕЛЬ ПОДТВЕРЖДАЕТ ПОЛУЧЕНИЕ =================

@router.callback_query(F.data == "confirm_gift")
async def buyer_confirms_gift(call: CallbackQuery, bot: Bot):
    # Ищем активную оплаченную сделку, где этот юзер — покупатель
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

    # Уведомление продавцу
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