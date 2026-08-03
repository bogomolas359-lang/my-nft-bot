from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from texts import t

def main_menu_kb(lang, is_admin=False):
    kb = [
        [InlineKeyboardButton(text=t(lang, "create_deal"), callback_data="create_deal")],
        [InlineKeyboardButton(text=t(lang, "change_lang"), callback_data="change_lang")],
        [InlineKeyboardButton(text=t(lang, "credentials"), callback_data="credentials")],
        [InlineKeyboardButton(text=t(lang, "support"), url="https://t.me/AlumixHelper")],
        [InlineKeyboardButton(text=t(lang, "about"), callback_data="about")],
    ]
    if is_admin:
        kb.insert(0, [InlineKeyboardButton(text=t(lang, "admin_panel"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def back_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu")]
    ])

def back_cancel_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "cancel"), callback_data="main_menu"),
         InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu")]
    ])

def payment_method_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "usdt_btn"), callback_data="pay_usdt")],
        [InlineKeyboardButton(text=t(lang, "ton_btn"), callback_data="pay_ton")],
        [InlineKeyboardButton(text=t(lang, "rub_btn"), callback_data="pay_rub")],
        [InlineKeyboardButton(text=t(lang, "stars_btn"), callback_data="pay_stars")],
        [InlineKeyboardButton(text="❌ " + t(lang, "cancel"), callback_data="main_menu")],
    ])

def join_deal_kb(deal_number, lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "join_deal"), callback_data=f"join:{deal_number}")],
    ])

def confirm_gift_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "confirm_gift_received"), callback_data="confirm_gift")],
    ])

def language_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ],
        [InlineKeyboardButton(text="◀️ Back", callback_data="main_menu")]
    ])

def credentials_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "edit_stars"), callback_data="edit_stars")],
        [InlineKeyboardButton(text=t(lang, "edit_card"), callback_data="edit_card")],
        [InlineKeyboardButton(text=t(lang, "edit_usdt"), callback_data="edit_usdt")],
        [InlineKeyboardButton(text=t(lang, "edit_ton"), callback_data="edit_ton")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu")],
    ])

def admin_main_kb(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 " + "Сделки" if lang == "ru" else "Deals", callback_data="admin_deals")],
        [InlineKeyboardButton(text=t(lang, "admin_add"), callback_data="admin_add")],
        [InlineKeyboardButton(text=t(lang, "admin_remove"), callback_data="admin_remove")],
        [InlineKeyboardButton(text=t(lang, "admin_list"), callback_data="admin_list")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="main_menu")],
    ])

def admin_deals_kb(deals, lang):
    kb = []
    for d in deals[:20]:  # limit
        kb.append([InlineKeyboardButton(
            text=t(lang, "confirm_payment_btn", deal_number=d["deal_number"]),
            callback_data=f"confirm_deal:{d['deal_number']}"
        )])
    kb.append([InlineKeyboardButton(text=t(lang, "back"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)