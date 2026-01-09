import os
import asyncio
import uuid
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from yt_dlp import YoutubeDL

# ================== КОНФИГУРАЦИЯ ==================
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL")  # Например, https://my-bot.onrender.com
PORT = int(os.getenv("PORT", 5000))

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher()
router = Router()

# Временное хранилище ссылок (в идеале использовать Redis)
user_data = {}
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]

# ================== СКАЧИВАНИЕ (Асинхронная обертка) ==================
async def download_soundcloud(query: str):
    uid = str(uuid.uuid4())[:8]
    path = f"downloads/{uid}.mp3"
    
    if not os.path.exists("downloads"):
        os.makedirs("downloads")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"downloads/{uid}.%(ext)s",
        "default_search": "scsearch",
        "noplaylist": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
    }

    # Запускаем блокирующую операцию скачивания в отдельном потоке
    loop = asyncio.get_event_loop()
    def run_ydl():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=True)
            if 'entries' in info:
                info = info['entries'][0]
            return info.get("title", "Music")

    title = await loop.run_in_executor(None, run_ydl)
    return path, title

# ================== ОБРАБОТЧИКИ AIOGRAM ==================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🎵 <b>Aiogram Music Bot</b>\n\nПришли название трека для поиска в SoundCloud.")

@router.message(F.text)
async def search_track(message: types.Message):
    query = message.text.strip()
    wait_msg = await message.answer(f"🔎 Ищу <b>{query}</b>...")

    try:
        loop = asyncio.get_event_loop()
        def get_info():
            with YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                return ydl.extract_info(f"scsearch6:{query}", download=False).get("entries", [])

        results = await loop.run_in_executor(None, get_info)

        if not results:
            await wait_msg.edit_text("❌ Ничего не найдено.")
            return

        kb = []
        text = "<b>🎶 Результаты поиска:</b>\n\n"
        
        for i, item in enumerate(results):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = item["url"]
            text += f"{EMOJI_NUMS[i]} {item['title'][:50]}...\n"
            kb.append([InlineKeyboardButton(text=EMOJI_NUMS[i], callback_data=f"dl_{rid}")])

        await wait_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@router.callback_query(F.data.startswith("dl_"))
async def handle_dl(callback: types.CallbackQuery):
    key = callback.data.split("_")[1]
    url = user_data.get(key)

    if not url:
        await callback.answer("Данные устарели, повторите поиск.", show_alert=True)
        return

    await callback.message.edit_text("⬇️ Начинаю загрузку...")

    try:
        path, title = await download_soundcloud(url)
        
        # Отправляем файл
        audio_file = types.FSInputFile(path, filename=f"{title}.mp3")
        await callback.message.answer_audio(audio=audio_file, caption=f"✅ {title}")
        
        # Чистим за собой
        if os.path.exists(path):
            os.remove(path)
        await callback.message.delete()
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка скачивания: {e}")

# ================== WEBHOOK SETUP ==================

async def on_startup(bot: Bot):
    await bot.set_webhook(f"{APP_URL}/webhook")

def main():
    dp.include_router(router)
    dp.startup.register(on_startup)

    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
