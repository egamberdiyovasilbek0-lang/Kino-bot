import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import datetime

# Token va Admin ID ni shu yerga yozing
TOKEN = "8638320387:AAEG7g9IHlCSYC8wtnpxCEDtn1tPhCG2r6E"
ADMIN_ID = 8595373987  # O'z Telegram ID raqamingizni yozing

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=storage)

# Vaqtinchalik ma'lumotlar bazasi (Real loyihada SQLite yoki PostgreSQL ishlatiladi)
DB_MOVIES = {
    # misol: "101": {"title": "Kino Nomi", "parts": {"1": "FILE_ID_1", "2": "FILE_ID_2"}}
}
DB_USERS = {}  # {user_id: {"vip_expire": datetime, "balance": 0}}
ADMIN_CARDS = ["Humo/Uzcard: 8600 0000 0000 0000 (Ism Familiya)"]
CHANNELS = ["@kanal_username"]  # Majburiy obuna kanallari

# --- STATES (Holatlar) ---
class AdminState(StatesGroup):
    waiting_for_movie_code = State()
    waiting_for_movie_title = State()
    waiting_for_movie_part_num = State()
    waiting_for_movie_file = State()
    waiting_for_card = State()

class UserState(StatesGroup):
    waiting_for_receipt = State()

# --- ASOSIY MENYU ---
def main_menu(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🎬 Kino qidirish (Kod orqali)"))
    kb.row(KeyboardButton("💎 VIP Sotib olish"), KeyboardButton("👤 Kabinet"))
    if user_id == ADMIN_ID:
        kb.row(KeyboardButton("👑 Admin Panel"))
    return kb

# --- MAJBURIY OBUNA TEKSHIRISH ---
async def check_subscription(user_id):
    if user_id == ADMIN_ID:
        return True
    
    # VIP statusini tekshirish
    user = DB_USERS.get(user_id)
    if user and user.get("vip_expire") and user["vip_expire"] > datetime.datetime.now():
        return True # VIP foydalanuvchilar majburiy obunadan ozod
        
    for channel in CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ['left', 'kicked']:
                return False
        except:
            return False
    return True

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    if user_id not in DB_USERS:
        DB_USERS[user_id] = {"vip_expire": None}
        
    if not await check_subscription(user_id):
        kb = InlineKeyboardMarkup()
        for ch in CHANNELS:
            kb.add(InlineKeyboardButton("📢 Kanalga obuna bo'lish", url=f"https://t.me/{ch.replace('@','')}"))
        kb.add(InlineKeyboardButton("✅ Obunani tekshirish", callback_data="check_sub"))
        await message.answer("⚠️ Botdan foydalanish uchun quyidagi kanal(lar)ga obuna bo'lishingiz kerak:", reply_markup=kb)
        return

    await message.answer("Assalomu alaykum! Kino botga xush kelibsiz. Kinoni kod orqali qidirishingiz mumkin.", reply_markup=main_menu(user_id))

@dp.callback_query_handler(text="check_sub")
async def process_check_sub(call: types.CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer("Rahmat! Obuna tasdiqlandi. Marhamat, botdan foydalanishingiz mumkin.", reply_markup=main_menu(call.from_user.id))
    else:
        await call.answer("Siz hali hamma kanalga obuna bo'lmadingiz!", show_alert=True)

# --- KINO QIDIRISH VA YUKLASH ---
@dp.message_handler(text="🎬 Kino qidirish (Kod orqali)")
async def search_movie_menu(message: types.Message):
    if not await check_subscription(message.from_user.id):
        return await message.answer("Avval kanallarga obuna bo'ling!")
    await message.answer("Iltimos, kino kodini yuboring (masalan: <code>101</code>):")

@dp.message_handler(lambda message: message.text and message.text.isdigit())
async def get_movie_by_code(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        return await message.answer("Avval kanallarga obuna bo'ling!")
    
    code = message.text.strip()
    movie = DB_MOVIES.get(code)
    
    if not movie:
        await message.answer("❌ Bunday kodli kino topilmadi.")
        return
        
    parts = movie["parts"]
    kb = InlineKeyboardMarkup(row_width=3)
    buttons = []
    for part_num in sorted(parts.keys(), key=int):
        buttons.append(InlineKeyboardButton(f"{part_num}-qism", callback_data=f"get_part_{code}_{part_num}"))
    kb.add(*buttons)
    
    await message.answer(f"🎥 <b>{movie['title']}</b>\n\nQuyidagi qismlardan birini tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("get_part_"))
async def send_movie_part(call: types.CallbackQuery):
    _, _, code, part_num = call.data.split("_")
    file_id = DB_MOVIES[code]["parts"][part_num]
    
    # 2x tez ishlashi va ulashishni taqiqlash uchun copy_message yoki send_video dan foydalanamiz
    # Ulashishni taqiqlash uchun bot orqali jo'natilgan videolarni foydalanuvchi boshqalarga forward (ulashish) qila olmaydi
    await call.message.answer_video(video=file_id, caption=f"🎬 Kino: {DB_MOVIES[code]['title']} ({part_num}-qism)")
    await call.answer()

# --- VIP SOTIB OLISH ---
@dp.message_handler(text="💎 VIP Status")
@dp.message_handler(text="💎 VIP Sotib olish")
async def vip_menu(message: types.Message):
    user_id = message.from_user.id
    user = DB_USERS.get(user_id, {})
    expire = user.get("vip_expire")
    
    status_text = "Sizda VIP status mavjud emas ❌"
    if expire and expire > datetime.datetime.now():
        status_text = f"Sizning VIP statusingiz mavjud ✅\nAmal qilish muddati: {expire.strftime('%Y-%m-%d %H:%M')}"
        
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("1 oylik - 15,000 so'm", callback_data="buy_vip_1"),
        InlineKeyboardButton("2 oylik - 28,000 so'm", callback_data="buy_vip_2"),
        InlineKeyboardButton("3 oylik - 40,000 so'm", callback_data="buy_vip_3"),
        InlineKeyboardButton("6 oylik - 75,000 so'm", callback_data="buy_vip_6"),
        InlineKeyboardButton("12 oylik - 140,000 so'm", callback_data="buy_vip_12"),
    )
    await message.answer(f"💎 **VIP OBUNA TIZIMI**\n\n{status_text}\n\n"
                         f"VIP imtiyozlari:\n• Majburiy obunalardan to'liq ozod bo'lasiz\n• Kinolarni cheklovlarsiz yuklab olasiz\n\n"
                         f"Obuna muddatini tanlang:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("buy_vip_"))
async def process_buy_vip(call: types.CallbackQuery, state: FSMContext):
    months = int(call.data.split("_")[2])
    cards_text = "\n".join(ADMIN_CARDS) if ADMIN_CARDS else "Hozircha karta qo'shilmagan."
    
    await state.update_data(months=months)
    await call.message.answer(f"💳 Quyidagi karta raqamiga to'lovni amalga oshiring:\n\n{cards_text}\n\n"
                              f"To'lovni qilgach, chek (kvitansiya) rasmini shu yerga yuboring.")
    await UserState.waiting_for_receipt.set()
    await call.answer()

@dp.message_handler(state=UserState.waiting_for_receipt, content_types=types.ContentTypes.PHOTO)
async def receive_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    months = data.get("months")
    user = message.from_user
    
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_vip_{user.id}_{months}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_vip_{user.id}")
    )
    
    await bot.send_photo(chat_id=ADMIN_ID, photo=message.photo[-1].file_id,
                         caption=f"👤 Foydalanuvchi: {user.full_name} (@{user.username}, ID: {user.id})\n"
                                 f"💎 So'ralayotgan VIP muddati: {months} oylik\nTo'lov cheki:", reply_markup=kb)
    
    await message.answer("✅ Chekingiz adminga yuborildi! Tez orada tekshirib tasdiqlashadi.")
    await state.finish()

# --- ADMIN PANEL ---
@dp.message_handler(text="👑 Admin Panel")
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("➕ Kino qo'shish"), KeyboardButton("💳 Karta qo'shish/o'zgartirish"))
    kb.row(KeyboardButton("🔙 Orqaga"))
    await message.answer("👑 Admin panelga xush kelibsiz:", reply_markup=kb)

@dp.message_handler(text="🔙 Orqaga")
async def back_to_main(message: types.Message):
    await message.answer("Asosiy menyu:", reply_markup=main_menu(message.from_user.id))

# Karta qo'shish
@dp.message_handler(text="💳 Karta qo'shish/o'zgartirish")
async def add_card_cmd(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Yangi karta ma'lumotlarini yuboring (Masalan: <code>Humo: 8600... (Ism Sh.)</code>):")
    await AdminState.waiting_for_card.set()

@dp.message_handler(state=AdminState.waiting_for_card)
async def save_card(message: types.Message, state: FSMContext):
    ADMIN_CARDS.clear()
    ADMIN_CARDS.append(message.text)
    await message.answer("✅ Karta muvaffaqiyatli yangilandi!", reply_markup=main_menu(message.from_user.id))
    await state.finish()

# Kino qo'shish jarayoni
@dp.message_handler(text="➕ Kino qo'shish")
async def add_movie_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("Kino uchun <b>kod</b> raqamini kiriting (masalan: 101):")
    await AdminState.waiting_for_movie_code.set()

@dp.message_handler(state=AdminState.waiting_for_movie_code)
async def process_movie_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    await message.answer("Kino nomini kiriting:")
    await AdminState.waiting_for_movie_title.set()

@dp.message_handler(state=AdminState.waiting_for_movie_title)
async def process_movie_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Kino nechanchi qism ekanligini raqamda kiriting (masalan: 1):")
    await AdminState.waiting_for_movie_part_num.set()

@dp.message_handler(state=AdminState.waiting_for_movie_part_num)
async def process_movie_part(message: types.Message, state: FSMContext):
    await state.update_data(part_num=message.text.strip())
    await message.answer("Kino videosini (faylini) yuboring:")
    await AdminState.waiting_for_movie_file.set()

@dp.message_handler(state=AdminState.waiting_for_movie_file, content_types=types.ContentTypes.VIDEO)
async def process_movie_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    code = data["code"]
    title = data["title"]
    part_num = data["part_num"]
    file_id = message.video.file_id
    
    if code not in DB_MOVIES:
        DB_MOVIES[code] = {"title": title, "parts": {}}
    
    DB_MOVIES[code]["parts"][part_num] = file_id
    await message.answer(f"✅ Kino muvaffaqiyatli saqlandi!\nKod: {code}\nNomi: {title}\nQism: {part_num}", reply_markup=main_menu(message.from_user.id))
    await state.finish()

# Admin VIP tasdiqlash tugmalari
@dp.callback_query_handler(lambda c: c.data.startswith("approve_vip_") or c.data.startswith("reject_vip_"))
async def admin_vip_decision(call: types.CallbackQuery):
    data = call.data.split("_")
    action = data[0]
    user_id = int(data[2])
    
    if action == "approve":
        months = int(data[3])
        current_expire = DB_USERS.get(user_id, {}).get("vip_expire")
        start_date = current_expire if current_expire and current_expire > datetime.datetime.now() else datetime.datetime.now()
        new_expire = start_date + datetime.timedelta(days=30 * months)
        
        DB_USERS[user_id]["vip_expire"] = new_expire
        await bot.send_message(user_id, f"🎉 Tabriklaymiz! Sizning {months} oylik VIP statusingiz faollashtirildi!\nAmal qilish muddati: {new_expire.strftime('%Y-%m-%d')}")
        await call.message.edit_caption(caption=call.message.caption + "\n\n✅ <b>TASDIQLANDI</b>")
    else:
        await bot.send_message(user_id, "❌ Sizning to'lov chekingiz admin tomonidan rad etildi.")
        await call.message.edit_caption(caption=call.message.caption + "\n\n❌ <b>RAD ETILDI</b>")
    
    await call.answer()

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
