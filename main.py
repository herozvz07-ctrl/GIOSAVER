import os
import asyncio
import uuid
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from yt_dlp import YoutubeDL

# ================== НАСТРОЙКИ ==================
TOKEN = os.getenv("BOT_TOKEN")
APP_URL = os.getenv("APP_URL") 
raw_port = os.getenv("PORT")
PORT = int(raw_port) if raw_port and raw_port.strip() else 5000

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()
router = Router()

user_data = {}
EMOJI_NUMS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

# ================== ЛОГИКА СКАЧИВАНИЯ ==================
async def download_media(url: str, mode="audio"):
    uid = str(uuid.uuid4())[:8]
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    
    # Настройки для видео (Insta/TikTok) или Аудио (YouTube)
    if mode == "video":
        path = f"downloads/{uid}.mp4"
        ydl_opts = {
            'format': 'best',
            'outtmpl': path,
            'quiet': True,
        }
    else:
        path = f"downloads/{uid}.mp3"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"downloads/{uid}.%(ext)s",
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }

    loop = asyncio.get_event_loop()
    def run_ydl():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info.get("title", "Файл"), path
            
    return await loop.run_in_executor(None, run_ydl)

# ================== ОБРАБОТЧИКИ ==================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "✨ <b>Добро пожаловать!</b>\n\n"
        "Я помогу тебе найти музыку или скачать видео.\n"
        "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        "🔹 <b>Просто напиши название песни</b>\n"
        "🔹 <b>Или скинь ссылку (Instagram Reels / TikTok)</b>",
    )

@router.message(F.text)
async def handle_message(message: types.Message):
    query = message.text.strip()
    
    # Если это ссылка (Instagram/TikTok/YouTube)
    if query.startswith(("http://", "https://")):
        wait_msg = await message.answer("⏳ <i>Обрабатываю ссылку...</i>")
        try:
            # Скачиваем видео
            title, path = await download_media(query, mode="video")
            video = FSInputFile(path)
            
            # Кнопка "Найти музыку" под видео
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎵 Найти музыку из видео", callback_data=f"search_music")
            ]])
            
            await message.answer_video(video=video, caption=f"✅ <b>{title}</b>", reply_markup=kb)
            await wait_msg.delete()
            if os.path.exists(path): os.remove(path)
        except Exception as e:
            await wait_msg.edit_text(f"⚠️ Не удалось скачать видео.\nВозможно, профиль закрыт.")
        return

    # Если это просто текст — ищем музыку
    wait_msg = await message.answer(f"🔍 Ищу <b>{query}</b>...")
    try:
        loop = asyncio.get_event_loop()
        def get_yt():
            # Поиск через YouTube (ytsearch)
            with YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                return ydl.extract_info(f"ytsearch8:{query}", download=False).get("entries", [])

        results = await loop.run_in_executor(None, get_yt)
        if not results:
            await wait_msg.edit_text("❌ Ничего не найдено.")
            return

        # Формируем сетку кнопок 4 в ряд
        buttons = []
        text = "<b>🎶 Выберите подходящий трек:</b>\n\n"
        
        row = []
        for i, item in enumerate(results):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = item["url"]
            text += f"{EMOJI_NUMS[i]} {item['title'][:40]}...\n"
            
            row.append(InlineKeyboardButton(text=EMOJI_NUMS[i], callback_data=f"dl_{rid}"))
            if len(row) == 4: # По 4 кнопки в ряд
                buttons.append(row)
                row = []
        if row: buttons.append(row)

        await wait_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

    except Exception as e:
        await message.answer("❌ Произошла ошибка при поиске.")

@router.callback_query(F.data.startswith("dl_"))
async def handle_dl(callback: types.CallbackQuery):
    url = user_data.get(callback.data.split("_")[1])
    if not url:
        await callback.answer("Ошибка: поиск устарел.")
        return

    await callback.message.edit_text("📥 <b>Загрузка трека...</b>")
    try:
        title, path = await download_media(url, mode="audio")
        audio = FSInputFile(path)
        await callback.message.answer_audio(audio=audio, caption=f"🎶 <b>{title}</b>")
        if os.path.exists(path): os.remove(path)
        await callback.message.delete()
    except Exception as e:
        await callback.message.answer("❌ Ошибка при скачивании.")

@router.callback_query(F.data == "search_music")
async def find_vid_music(callback: types.CallbackQuery):
    await callback.answer("Эта функция будет искать музыку из Reels (в разработке)", show_alert=True)

# ================== ЗАПУСК ==================
async def on_startup(bot: Bot):
    await bot.set_webhook(f"{APP_URL}/webhook")

def main():
    dp.include_router(router)
    dp.startup.register(on_startup)
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    main()
        
