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

# ================== УЛУЧШЕННАЯ ЛОГИКА СКАЧИВАНИЯ ==================
async def download_media(url: str, mode="audio"):
    uid = str(uuid.uuid4())[:8]
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    
    if mode == "video":
        output_template = f"downloads/{uid}.mp4"
        ydl_opts = {
            'format': 'best',
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
        }
    else:
        # Для аудио важно правильно указать пост-процессинг
        output_template = f"downloads/{uid}.%(ext)s"
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
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
            title = info.get("title", "Unknown")
            # yt-dlp меняет расширение после обработки, проверяем итоговый файл
            final_path = f"downloads/{uid}.mp4" if mode == "video" else f"downloads/{uid}.mp3"
            return title, final_path
            
    return await loop.run_in_executor(None, run_ydl)

# ================== ОБРАБОТЧИКИ ==================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎧 <b>Music & Video Saver</b>\n\n"
        "• Пришли <b>название</b> — чтобы найти музыку\n"
        "• Пришли <b>ссылку</b> — чтобы скачать Reels/TikTok\n"
    )

@router.message(F.text)
async def handle_message(message: types.Message):
    query = message.text.strip()
    
    if query.startswith(("http", "https")):
        wait_msg = await message.answer("⏳ <i>Скачиваю видео...</i>")
        try:
            title, path = await download_media(query, mode="video")
            video = FSInputFile(path)
            
            # Кнопка извлечения звука (передаем URL)
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🎵 Вырезать звук", callback_data=f"extaudio_{uuid.uuid4().hex[:8]}")
            ]])
            # Сохраняем URL видео для извлечения звука
            user_data[list(kb.inline_keyboard[0][0].callback_data.split('_'))[1]] = query
            
            await message.answer_video(video=video, caption=f"✅ {title}", reply_markup=kb)
            await wait_msg.delete()
            if os.path.exists(path): os.remove(path)
        except Exception as e:
            print(f"Error Video: {e}")
            await wait_msg.edit_text("⚠️ Ошибка. Проверь, что ссылка открыта.")
        return

    # Поиск музыки
    wait_msg = await message.answer(f"🔍 Ищу <b>{query}</b>...")
    try:
        def get_yt():
            with YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
                return ydl.extract_info(f"ytsearch8:{query}", download=False).get("entries", [])

        results = await asyncio.get_event_loop().run_in_executor(None, get_yt)
        if not results:
            await wait_msg.edit_text("❌ Ничего не найдено.")
            return

        buttons = []
        text = "<b>🎶 Результаты поиска:</b>\n\n"
        row = []
        for i, item in enumerate(results):
            rid = str(uuid.uuid4())[:8]
            user_data[rid] = item["url"]
            text += f"{EMOJI_NUMS[i]} {item['title'][:45]}\n"
            row.append(InlineKeyboardButton(text=EMOJI_NUMS[i], callback_data=f"dl_{rid}"))
            if len(row) == 4:
                buttons.append(row)
                row = []
        if row: buttons.append(row)

        await wait_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    except Exception as e:
        print(f"Error Search: {e}")
        await wait_msg.edit_text("❌ Ошибка поиска.")

@router.callback_query(F.data.startswith("dl_"))
async def handle_dl(callback: types.CallbackQuery):
    rid = callback.data.split("_")[1]
    url = user_data.get(rid)
    if not url:
        await callback.answer("Ошибка: попробуй найти заново.")
        return

    await callback.message.edit_text("📥 <b>Загрузка...</b>")
    try:
        title, path = await download_media(url, mode="audio")
        await callback.message.answer_audio(audio=FSInputFile(path), caption=f"🎶 {title}")
        if os.path.exists(path): os.remove(path)
        await callback.message.delete()
    except Exception as e:
        print(f"Error Download: {e}")
        await callback.message.answer("❌ Ошибка при конвертации в MP3.")

@router.callback_query(F.data.startswith("extaudio_"))
async def extract_audio_callback(callback: types.CallbackQuery):
    rid = callback.data.split("_")[1]
    url = user_data.get(rid)
    if not url:
        await callback.answer("Ссылка потеряна, скинь видео еще раз.")
        return

    await callback.answer("Извлекаю звук...")
    try:
        title, path = await download_media(url, mode="audio")
        await callback.message.answer_audio(audio=FSInputFile(path), caption=f"🎵 Звук из видео: {title}")
        if os.path.exists(path): os.remove(path)
    except Exception as e:
        await callback.message.answer("❌ Не удалось извлечь звук.")

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
        
