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

# ================== ЛОГИКА ==================
async def download_media(url: str, mode="audio"):
    uid = str(uuid.uuid4())[:8]
    if not os.path.exists("downloads"): os.makedirs("downloads")
    
    if mode == "video":
        path = f"downloads/{uid}.mp4"
        ydl_opts = {'format': 'best', 'outtmpl': path, 'quiet': True}
    else:
        path = f"downloads/{uid}.mp3"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f"downloads/{uid}.%(ext)s",
            'quiet': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }

    loop = asyncio.get_event_loop()
    def run_ydl():
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Возвращаем название и путь. Для аудио yt-dlp сам допишет .mp3
            return info.get("title", "Music"), (path if mode == "video" else f"downloads/{uid}.mp3")
            
    return await loop.run_in_executor(None, run_ydl)

# ================== ОБРАБОТЧИКИ ==================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("✨ <b>Пришли название песни или ссылку на видео!</b>")

@router.message(F.text)
async def handle_message(message: types.Message):
    query = message.text.strip()
    
    # ЕСЛИ ССЫЛКА (Reels/TikTok)
    if query.startswith(("http", "https")):
        wait_msg = await message.answer("⏳ <i>Загружаю видео...</i>")
        try:
            with YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
                info = ydl.extract_info(query, download=False)
                video_title = info.get('title', 'Video')
            
            title, path = await download_media(query, mode="video")
            
            # Кнопка "Найти полную песню"
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔍 Найти полную песню", callback_data=f"findfull_{uuid.uuid4().hex[:8]}")
            ]])
            user_data[list(kb.inline_keyboard[0][0].callback_data.split('_'))[1]] = video_title
            
            await message.answer_video(video=FSInputFile(path), caption=f"✅ {title}", reply_markup=kb)
            await wait_msg.delete()
            if os.path.exists(path): os.remove(path)
        except Exception:
            await wait_msg.edit_text("❌ Ошибка загрузки видео.")
        return

    # ПОИСК МУЗЫКИ ПО ТЕКСТУ
    wait_msg = await message.answer(f"🔍 Ищу: <b>{query}</b>...")
    try:
        def get_yt():
            with YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                return ydl.extract_info(f"ytsearch8:{query}", download=False).get("entries", [])

        results = await asyncio.get_event_loop().run_in_executor(None, get_yt)
        if not results:
            return await wait_msg.edit_text("❌ Не найдено.")

        buttons, text, row = [], "<b>🎶 Что именно скачать?</b>\n\n", []
        for i, item in enumerate(results):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = item["url"]
            text += f"{EMOJI_NUMS[i]} {item['title'][:40]}\n"
            row.append(InlineKeyboardButton(text=EMOJI_NUMS[i], callback_data=f"dl_{rid}"))
            if len(row) == 4:
                buttons.append(row); row = []
        if row: buttons.append(row)
        await wait_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except:
        await wait_msg.edit_text("❌ Ошибка поиска.")

@router.callback_query(F.data.startswith("dl_"))
async def handle_dl(callback: types.CallbackQuery):
    url = user_data.get(callback.data.split("_")[1])
    await callback.message.edit_text("📥 <b>Конвертирую в MP3...</b>")
    try:
        title, path = await download_media(url, mode="audio")
        await callback.message.answer_audio(audio=FSInputFile(path), caption=f"🎶 {title}")
        if os.path.exists(path): os.remove(path)
        await callback.message.delete()
    except:
        await callback.message.answer("❌ Ошибка! Проверь FFmpeg Buildpack в настройках Render.")

@router.callback_query(F.data.startswith("findfull_"))
async def find_full_music(callback: types.CallbackQuery):
    # Берем название видео и ищем его как песню
    video_title = user_data.get(callback.data.split("_")[1])
    if video_title:
        await callback.message.answer(f"🔎 Ищу полную версию для: <b>{video_title}</b>")
        # Просто перенаправляем в поиск
        callback.message.text = video_title
        await handle_message(callback.message)
    await callback.answer()

# ================== ЗАПУСК ==================
async def on_startup(bot: Bot): await bot.set_webhook(f"{APP_URL}/webhook")

def main():
    dp.include_router(router)
    dp.startup.register(on_startup)
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    web.run_app(app, host="0.0.0.0", port=PORT)

if __name__ == "__main__": main()
        
