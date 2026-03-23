import asyncio
import random
import string
import sqlite3
import aiohttp

from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

# CONFIG
TOKEN = "YOUR_BOT_TOKEN"
CRYPTO_TOKEN = "YOUR_CRYPTOBOT_API_TOKEN"
CHANNEL_ID = -1001234567890
BOT_USERNAME = "your_bot_username"


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

  amount = State()
  game = State()
  amount = State()
  uses = State()
  min_dep = State()

# UTILS

def get_user(uid):
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
      cursor.execute("INSERT INTO invoices VALUES (?,?,?,0)", (inv["invoice_id"], uid, amount))
      conn.commit()
      return inv["pay_url"]

async def check_payments():
    await asyncio.sleep(10)
    cursor.execute("SELECT * FROM invoices WHERE paid=0")
      async with aiohttp.ClientSession() as s:
        headers = {"Crypto-Pay-API-Token": CRYPTO_TOKEN}
        async with s.get(f"https://pay.crypt.bot/api/getInvoices?invoice_ids={iid}", headers=headers) as r:
          data = await r.json()
          try:
            if data["result"]["items"][0]["status"] == "paid":
              cursor.execute("UPDATE invoices SET paid=1 WHERE invoice_id=?", (iid,))
              conn.commit()
              await bot.send_message(uid, f"💰 +{amount}$")
          except:
            pass


def menu():
  return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
    [InlineKeyboardButton(text="🎲 Игры", callback_data="games")]
  ])

# START
@dp.message(CommandStart())
  user = get_user(m.from_user.id)
  await m.answer("🎰 Казино", reply_markup=menu())

# PROFILE

@dp.callback_query(F.data == "profile")
async def profile(c: CallbackQuery):
  u = get_user(c.from_user.id)
  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💳 Пополнить", callback_data="dep")],
  ])
  await c.message.edit_text(f"ID: {u[0]}\nБаланс: {u[1]}$", reply_markup=kb)

# GAMES MENU

@dp.callback_query(F.data == "games")
async def games(c: CallbackQuery):
  kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🎲 Чёт", callback_data="even")],
    [InlineKeyboardButton(text="💥 7x5", callback_data="seven")],
    [InlineKeyboardButton(text="🐋 Кит x100", callback_data="whale")],
    [InlineKeyboardButton(text="🔥 36x5", callback_data="prod36")]
  ])
  await c.message.edit_text("🎲 Выбери игру", reply_markup=kb)

# BET STATE

@dp.callback_query(F.data.in_(["even","odd","seven","whale","prod36"]))
async def choose_game(c: CallbackQuery, state: FSMContext):
  await state.update_data(game=c.data)
  await state.set_state(BetState.amount)
  await c.message.answer("💰 Введи ставку:")

  if game == "even":
      w = win(2)
    else:
  # ODD x2
    d = random.randint(1,6)
      update_balance(m.from_user.id, w)
      await m.answer(f"🎲 {d} LOSE")
  if game == "seven":
    if d1 + d2 == 7:
      w = win(5)
      update_balance(m.from_user.id, w)
      await m.answer(f"🎲 {d1}+{d2} WIN +{round(w,2)}$")
    else:
      await m.answer(f"🎲 {d1}+{d2} LOSE")

  # WHALE x100 (1%)
  if game == "whale":
    roll = random.randint(1, 100)
    if roll == 100:
      w = win(100)
      update_balance(m.from_user.id, w)
      await m.answer(f"🐋 {roll} JACKPOT +{round(w,2)}$")
    else:
      await m.answer(f"🐋 {roll} LOSE")
      w = win(5)
      await m.answer(f"💥 {d1}x{d2} WIN +{round(w,2)}$")
    else:
      await m.answer(f"💥 {d1}x{d2} LOSE")

  await state.clear()

# RUN

async def main():
  asyncio.create_task(check_payments())
  await dp.start_polling(bot)
