from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from texts import t


def main_menu_kb(lang, is_admin=False):
    kb = [
        [InlineKeyboardButton(text=t(lang, "create_deal"), callback_data="create_deal")],
        [InlineKeyboardButton(text=t(lang, "balance_btn"), callback_data="balance")],
        [InlineKeyboardButton(text=t(lang, "change_lang"), callback_data="change_lang")],
        [InlineKeyboardButton(text=t(lang, "credentials"), callback_data="credentials")],
        [InlineKeyboardButton(text=t(lang, "support"), url="https://t.me/alumixHelp")],
        [InlineKeyboardButton(text=t(lang, "about"), callback_data="about")],
    ]
    if is_admin:
        kb.insert(0, [InlineKeyboardButton(text=t(lang, "admin_panel"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ " + t(lang, "back"), callback_data="main_menu")]
    ])


def back_cancel_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ " + t(lang, "cancel"), callback_data="cancel_state")],
        [InlineKeyboardButton(text="◀️ " + t(lang, "back"), callback_data="main_menu")]
    ])


def payment_method_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "usdt_btn"), callback_data="pay_usdt")],
        [InlineKeyboardButton(text=t(lang, "ton_btn"), callback_data="pay_ton")],
        [InlineKeyboardButton(text=t(lang, "rub_btn"), callback_data="pay_rub")],
        [InlineKeyboardButton(text=t(lang, "sbp_btn"), callback_data="pay_sbp")],
        [InlineKeyboardButton(text=t(lang, "uah_btn"), callback_data="pay_uah")],
        [InlineKeyboardButton(text=t(lang, "stars_btn"), callback_data="pay_stars")],
        [InlineKeyboardButton(text="❌ " + t(lang, "cancel"), callback_data="main_menu")],
    ])


def join_deal_kb(deal_number, lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "join_deal"), callback_data=f"join:{deal_number}")],
        [InlineKeyboardButton(text="◀️ " + t(lang, "back"), callback_data="main_menu")]
    ])


def confirm_gift_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "confirm_gift"), callback_data="confirm_gift")]
    ])


def language_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ]
    ])


def credentials_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Изменить карту (RUB)", callback_data="edit_card")],
        [InlineKeyboardButton(text="📱 Изменить СБП", callback_data="edit_sbp")],
        [InlineKeyboardButton(text="🇺🇦 Изменить карту (UAH)", callback_data="edit_uah")],
        [InlineKeyboardButton(text="⭐ Изменить Stars", callback_data="edit_stars")],
        [InlineKeyboardButton(text="💵 Изменить USDT", callback_data="edit_usdt")],
        [InlineKeyboardButton(text="💎 Изменить TON", callback_data="edit_ton")],
        [InlineKeyboardButton(text="◀️ " + t(lang, "back"), callback_data="main_menu")]
    ])


def admin_main_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Сделки" if lang == "ru" else "📋 Deals", callback_data="admin_deals")],
        [InlineKeyboardButton(text="💸 Заявки на вывод" if lang == "ru" else "💸 Withdrawals", callback_data="admin_withdrawals")],
        [InlineKeyboardButton(text="➕ Добавить админа" if lang == "ru" else "➕ Add admin", callback_data="admin_add")],
        [InlineKeyboardButton(text="➖ Удалить админа" if lang == "ru" else "➖ Remove admin", callback_data="admin_remove")],
        [InlineKeyboardButton(text="👥 Список админов" if lang == "ru" else "👥 Admins list", callback_data="admin_list")],
        [InlineKeyboardButton(text="◀️ " + t(lang, "back"), callback_data="main_menu")]
    ])


def admin_deals_kb(deals, lang):
    kb = []
    for d in deals[:20]:
        status_emoji = "🟡" if d["status"] == "waiting_for_buyer" else "🔵" if d["status"] == "buyer_joined" else "✅"
        info_text = f"{status_emoji} #{d['deal_number']} | @{d['seller_username'] or '?'} | {d['amount']} {d['currency']}"
        kb.append([InlineKeyboardButton(text=info_text, callback_data=f"deal_info:{d['deal_number']}")])
        if d["buyer_id"] and d["status"] not in ["paid", "completed"]:
            kb.append([InlineKeyboardButton(
                text=f"💸 Подтвердить оплату #{d['deal_number']}",
                callback_data=f"confirm_deal:{d['deal_number']}"
            )])
    kb.append([InlineKeyboardButton(text="◀️ " + t(lang, "back"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)