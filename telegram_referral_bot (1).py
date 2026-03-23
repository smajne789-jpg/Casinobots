import asyncio
import random
import string
import sqlite3
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# CONFIG
TOKEN = "8527708140:AAF-1pD3LQ3B1tNBXH00rFSEQSllgpJY5W8"
CRYPTO_TOKEN = "555337:AA5FF4gvIkPM9skhu0gTTXrOrBqFnf7GDHN"
ADMIN_ID = 8034491282
CHANNEL_ID = -1003869807196
BOT_USERNAME = "PAVLUCK_BOT"
HOUSE_EDGE = 0.05

bot = Bot(token=TOKEN)
dp = Dispatcher()

# DB
conn = sqlite3.connect("casino.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0, total_deposit REAL DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS invoices (invoice_id TEXT, user_id INTEGER, amount REAL, paid INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS checks (code TEXT PRIMARY KEY, amount REAL, uses INTEGER, used INTEGER DEFAULT 0, min_dep REAL DEFAULT 0)")
conn.commit()

# STATES
class DepositState(StatesGroup):
    amount = State()

class BetState(StatesGroup):
    amount = State()
    game = State()

class CreateCheckState(StatesGroup):
    amount = State()
    uses = State()
    min_dep = State()

# UTILS

def get_user(uid):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (uid,))
        conn.commit()
        return (uid, 0, 0)
    return user


def update_balance(uid, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, uid))
    conn.commit()

# CRYPTO

async def create_invoice(uid, amount):
    async with aiohttp.ClientSession() as s:
        headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
        data = {"asset": "USDT", "amount": str(amount)}
        async with s.post("https://pay.crypt.bot/api/createInvoice", json=data, headers=headers) as r:
            res = await r.json()
            inv = res["result"]
            cursor.execute("INSERT INTO invoices VALUES (?,?,?,0)", (inv["invoice_id"], uid, amount))
            conn.commit()
            return inv["pay_url"]

async def check_payments():
    while True:
        await asyncio.sleep(10)
        cursor.execute("SELECT * FROM invoices WHERE paid=0")
        for iid, uid, amount, paid in cursor.fetchall():
            async with aiohttp.ClientSession() as s:
                headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
                async with s.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={iid}", headers=headers) as r:
                    data = await r.json()
                    try:
                        if data["result"]["items"][0]["status"] == "paid":
                            update_balance(uid, amount)
                            cursor.execute("UPDATE invoices SET paid=1 WHERE invoice_id=?", (iid,))
                            conn.commit()
                            await bot.send_message(uid, f"💰 +{amount}$")
                    except:
                        pass

# MENU

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🎲 Игры", callback_data="games")]
    ])

# START

@dp.message(CommandStart())
async def start(m: Message):
    args = m.text.split()
    user = get_user(m.from_user.id)

    if len(args) > 1 and args[1].startswith("check_"):
        code = args[1].split("_")[1]
        cursor.execute("SELECT * FROM checks WHERE code=?", (code,))
        check = cursor.fetchone()

        if check:
            _, amount, uses, used, min_dep = check

            if used >= uses:
                await m.answer("❌ Чек закончился")
                return

            if user[2] < min_dep:
                await m.answer(f"❌ Нужно пополнить минимум на {min_dep}$")
                return

            update_balance(m.from_user.id, amount)
            cursor.execute("UPDATE checks SET used = used + 1 WHERE code=?", (code,))
            conn.commit()

            await m.answer(f"🎟 +{amount}$")

    await m.answer("🎰 Казино", reply_markup=menu())

# PROFILE

@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
    u = get_user(c.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Пополнить", callback_data="dep")]
    ])
    await c.message.edit_text(f"ID: {u[0]}\nБаланс: {u[1]}$", reply_markup=kb)

# DEPOSIT

@dp.callback_query(F.data == "dep")
async def dep(c: CallbackQuery, state: FSMContext):
    await state.set_state(DepositState.amount)
    await c.message.answer("Сумма:")

@dp.message(DepositState.amount)
async def dep_amount(m: Message, state: FSMContext):
    amount = float(m.text)
    link = await create_invoice(m.from_user.id, amount)

    cursor.execute("UPDATE users SET total_deposit = total_deposit + ? WHERE user_id=?", (amount, m.from_user.id))
    conn.commit()

    await m.answer(link)
    await state.clear()

# GAMES

@dp.callback_query(F.data == "games")
async def games(c: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Чёт", callback_data="even")],
        [InlineKeyboardButton(text="7", callback_data="seven")],
        [InlineKeyboardButton(text="Нечёт", callback_data="odd")],
        [InlineKeyboardButton(text="🐋 Кит x100", callback_data="whale")]
    ])
    await c.message.edit_text("Игры", reply_markup=kb)

@dp.callback_query(F.data.in_(["even","seven","odd","whale"]))
async def choose_game(c: CallbackQuery, state: FSMContext):
    await state.update_data(game=c.data)
    await state.set_state(BetState.amount)
    await c.message.answer("Ставка:")

@dp.message(BetState.amount)
async def play(m: Message, state: FSMContext):
    data = await state.get_data()
    game = data["game"]
    bet = float(m.text)
try:
    bet = float(m.text)
except:
    await m.answer("❌ Введите число")
    return

if bet < 0.1:
    await m.answer("❌ Минимальная ставка 0.1$")
    return
    
    u = get_user(m.from_user.id)
    if u[1] < bet:
        await m.answer("Нет баланса")
        return

    update_balance(m.from_user.id, -bet)

    def win(mult): return bet * mult * (1 - HOUSE_EDGE)

    if game == "even":
        d = random.randint(1,6)
        if d%2==0:
            w = win(2)
            update_balance(m.from_user.id, w)
            await m.answer(f"{d} WIN {round(w,2)}$")
        else:
            await m.answer(f"{d} LOSE")

    if game == "odd":
        d = random.randint(1,6)
        if d % 2 != 0:
            w = win(2)
            update_balance(m.from_user.id, w)
            await m.answer(f"{d} WIN {round(w,2)}$")
        else:
            await m.answer(f"{d} LOSE")

    if game == "whale":
        chance = random.randint(1,100)
        if chance == 1:
            w = win(100)
            update_balance(m.from_user.id, w)
            await m.answer(f"🐋 ВЫПАЛ КИТ!!! WIN {round(w,2)}$")
        else:
            await m.answer("🌊 Пусто...")

    if game == "seven":
        d1,d2 = random.randint(1,6), random.randint(1,6)
        if d1+d2==7:
            w = win(5)
            update_balance(m.from_user.id, w)
            await m.answer(f"{d1}+{d2} WIN {round(w,2)}$")
        else:
            await m.answer(f"{d1}+{d2} LOSE")

    await state.clear()

# ADMIN PANEL (INLINE)

@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id != ADMIN_ID:
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎟 Создать чек", callback_data="create_check")]
    ])

    await m.answer("Админ панель", reply_markup=kb)

@dp.callback_query(F.data == "create_check")
async def create_check_start(c: CallbackQuery, state: FSMContext):
    await state.set_state(CreateCheckState.amount)
    await c.message.answer("Сумма чека:")

@dp.message(CreateCheckState.amount)
async def check_amount(m: Message, state: FSMContext):
    await state.update_data(amount=float(m.text))
    await state.set_state(CreateCheckState.uses)
    await m.answer("Кол-во активаций:")

@dp.message(CreateCheckState.uses)
async def check_uses(m: Message, state: FSMContext):
    await state.update_data(uses=int(m.text))
    await state.set_state(CreateCheckState.min_dep)
    await m.answer("Мин депозит (0 если нет):")

@dp.message(CreateCheckState.min_dep)
async def check_finish(m: Message, state: FSMContext):
    data = await state.get_data()

    code = ''.join(random.choices(string.digits, k=6))

    cursor.execute("INSERT INTO checks VALUES (?,?,?,?,?)", (
        code,
        data['amount'],
        data['uses'],
        0,
        float(m.text)
    ))
    conn.commit()

    link = f"https://t.me/{BOT_USERNAME}?start=check_{code}"
    await m.answer(f"✅ Чек создан:\n{link}")

    await state.clear()

# RUN

async def main():
    asyncio.create_task(check_payments())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
