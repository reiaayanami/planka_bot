import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
from datetime import date, datetime

TOKEN = "8542417036:AAFTTi_5SmzSht0-sYogrou9XpaqQaGmOZU"
DB = "planka.db"

bot = Bot(TOKEN)
dp = Dispatcher()

kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📝 Зареєструватись", callback_data="reg")],
    [InlineKeyboardButton(text="⬆️ +1", callback_data="up"),
     InlineKeyboardButton(text="⬇️ -1", callback_data="down")],
    [InlineKeyboardButton(text="📜 Лог", callback_data="log")]
])

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS registered (
                user_id INTEGER,
                chat_id INTEGER,
                PRIMARY KEY (user_id, chat_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS planka (
                chat_id INTEGER PRIMARY KEY,
                value INTEGER
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER,
                chat_id INTEGER,
                actions INTEGER,
                last_date TEXT,
                PRIMARY KEY (user_id, chat_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                chat_id INTEGER,
                user TEXT,
                action TEXT,
                time TEXT
            )
        """)
        await db.commit()

async def is_registered(user_id, chat_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT 1 FROM registered WHERE user_id=? AND chat_id=?",
            (user_id, chat_id)
        )
        return await cur.fetchone() is not None

async def get_planka(chat_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT value FROM planka WHERE chat_id=?", (chat_id,))
        row = await cur.fetchone()
        if not row:
            await db.execute("INSERT INTO planka VALUES (?,?)", (chat_id, 0))
            await db.commit()
            return 0
        return row[0]

async def get_user(user_id, chat_id):
    today = str(date.today())
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT actions,last_date FROM users WHERE user_id=? AND chat_id=?",
            (user_id, chat_id)
        )
        row = await cur.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO users VALUES (?,?,?,?)",
                (user_id, chat_id, 0, today)
            )
            await db.commit()
            return 0
        actions, last = row
        if last != today:
            actions = 0
            await db.execute(
                "UPDATE users SET actions=?, last_date=? WHERE user_id=? AND chat_id=?",
                (0, today, user_id, chat_id)
            )
            await db.commit()
        return actions

async def update(user_id, chat_id, delta, username):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE planka SET value=value+? WHERE chat_id=?", (delta, chat_id))
        await db.execute(
            "UPDATE users SET actions=actions+1 WHERE user_id=? AND chat_id=?",
            (user_id, chat_id)
        )
        await db.execute(
            "INSERT INTO logs VALUES (?,?,?,?)",
            (chat_id, username, f"{'+' if delta>0 else ''}{delta}", datetime.now().strftime("%d.%m %H:%M"))
        )
        await db.commit()

async def send_last_logs(chat_id):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "SELECT user,action,time FROM logs WHERE chat_id=? ORDER BY rowid DESC LIMIT 7",
            (chat_id,)
        )
        rows = await cur.fetchall()
    if rows:
        text = "📜 Останні 7 змін:\n" + "\n".join(f"{u}: {a} ({t})" for u, a, t in rows)
    else:
        text = "Лог порожній"
    await bot.send_message(chat_id, text)

@dp.message(Command("start"))
async def start(m: types.Message):
    v = await get_planka(m.chat.id)
    await m.answer(f"🏋️ Планка Максіма\nПоточна планка: {v}", reply_markup=kb)

@dp.callback_query()
async def cb(c: types.CallbackQuery):
    chat_id = c.message.chat.id
    user_id = c.from_user.id
    name = c.from_user.first_name

    if c.data == "reg":
        async with aiosqlite.connect(DB) as db:
            await db.execute(
                "INSERT OR IGNORE INTO registered VALUES (?,?)",
                (user_id, chat_id)
            )
            await db.commit()
        await c.answer("✅ Ти зареєстрований", show_alert=True)
        return

    if not await is_registered(user_id, chat_id):
        await c.answer("❌ Спочатку зареєструйся", show_alert=True)
        return

    if c.data in ("up", "down"):
        actions = await get_user(user_id, chat_id)
        if actions >= 3:
            await c.answer("❌ Ліміт 3/день", show_alert=True)
            return
        delta = 1 if c.data == "up" else -1
        await update(user_id, chat_id, delta, name)

    if c.data == "log":
        await send_last_logs(chat_id)  # Відправляємо останні зміни у чат
        await c.answer()
        return

    v = await get_planka(chat_id)
    await c.message.edit_text(f"🏋️ Планка Максіма\nПоточна планка: {v}", reply_markup=kb)
    await c.answer()

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
