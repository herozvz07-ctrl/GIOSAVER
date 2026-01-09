import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import requests
from flask import Flask
import threading

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask приложение для Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Токен бота (замените на свой)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# ID обязательных каналов для подписки
REQUIRED_CHANNELS = os.environ.get('CHANNELS', '').split(',')

# Тексты на разных языках
TEXTS = {
    'ru': {
        'start': '🎵 Добро пожаловать в Music Bot!\n\nОтправьте мне название песни для поиска.',
        'subscribe': '❌ Для использования бота подпишитесь на наши каналы:\n\n',
        'subscribed': '✅ Спасибо за подписку! Теперь отправьте название песни.',
        'searching': '🔍 Ищу: {}...',
        'found': '🎵 Найдено {} результатов:',
        'select': 'Выберите трек:',
        'downloading': '⏬ Загружаю...',
        'error': '❌ Ошибка: {}',
        'no_results': '😔 Ничего не найдено по запросу: {}',
        'settings': '⚙️ Настройки\n\nВыберите язык:',
        'lang_changed': '✅ Язык изменен на Русский',
        'top': '🔥 Топ хиты сегодня:',
        'check_sub': '✅ Проверить подписку'
    },
    'en': {
        'start': '🎵 Welcome to Music Bot!\n\nSend me a song name to search.',
        'subscribe': '❌ Please subscribe to our channels to use the bot:\n\n',
        'subscribed': '✅ Thanks for subscribing! Now send a song name.',
        'searching': '🔍 Searching: {}...',
        'found': '🎵 Found {} results:',
        'select': 'Select a track:',
        'downloading': '⏬ Downloading...',
        'error': '❌ Error: {}',
        'no_results': '😔 No results found for: {}',
        'settings': '⚙️ Settings\n\nSelect language:',
        'lang_changed': '✅ Language changed to English',
        'top': '🔥 Top hits today:',
        'check_sub': '✅ Check subscription'
    },
    'uz': {
        'start': '🎵 Music Bot ga xush kelibsiz!\n\nQo\'shiq nomini yuboring.',
        'subscribe': '❌ Botdan foydalanish uchun kanallarimizga obuna bo\'ling:\n\n',
        'subscribed': '✅ Obuna bo\'lganingiz uchun rahmat! Endi qo\'shiq nomini yuboring.',
        'searching': '🔍 Qidirilmoqda: {}...',
        'found': '🎵 {} natija topildi:',
        'select': 'Trekni tanlang:',
        'downloading': '⏬ Yuklanmoqda...',
        'error': '❌ Xatolik: {}',
        'no_results': '😔 Hech narsa topilmadi: {}',
        'settings': '⚙️ Sozlamalar\n\nTilni tanlang:',
        'lang_changed': '✅ Til O\'zbekchaga o\'zgartirildi',
        'top': '🔥 Bugungi top qo\'shiqlar:',
        'check_sub': '✅ Obunani tekshirish'
    }
}

# Хранилище пользовательских настроек
user_settings = {}

def get_user_lang(user_id):
    return user_settings.get(user_id, {}).get('lang', 'ru')

def get_text(user_id, key):
    lang = get_user_lang(user_id)
    return TEXTS[lang][key]

# Проверка подписки на каналы
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not REQUIRED_CHANNELS or REQUIRED_CHANNELS == ['']:
        return True
    
    for channel in REQUIRED_CHANNELS:
        if not channel.strip():
            continue
        try:
            member = await context.bot.get_chat_member(chat_id=channel.strip(), user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            continue
    
    return True

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_settings:
        user_settings[user_id] = {'lang': 'ru'}
    
    if not await check_subscription(update, context):
        keyboard = [[InlineKeyboardButton(get_text(user_id, 'check_sub'), callback_data='check_sub')]]
        text = get_text(user_id, 'subscribe')
        for channel in REQUIRED_CHANNELS:
            if channel.strip():
                text += f"• {channel}\n"
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    await update.message.reply_text(get_text(user_id, 'start'))

# Команда /settings
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("🇷🇺 Русский", callback_data='lang_ru')],
        [InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')],
        [InlineKeyboardButton("🇺🇿 O'zbek", callback_data='lang_uz')]
    ]
    
    await update.message.reply_text(
        get_text(user_id, 'settings'),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Команда /top
async def top_hits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not await check_subscription(update, context):
        keyboard = [[InlineKeyboardButton(get_text(user_id, 'check_sub'), callback_data='check_sub')]]
        await update.message.reply_text(get_text(user_id, 'subscribe'), reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Топ хиты (примерный список)
    top_songs = [
        "🎵 1. INSTASAMKA - За деньги да",
        "🎵 2. Miyagi & Andy Panda - Kosandra",
        "🎵 3. Скриптонит - Положение",
        "🎵 4. Элджей - Розовое вино",
        "🎵 5. Моргенштерн - Cadillac",
        "🎵 6. JONY - Комета",
        "🎵 7. Баста - Сансара",
        "🎵 8. Zivert - Life",
        "🎵 9. HammAli & Navai - Прятки",
        "🎵 10. T-Fest - Улети"
    ]
    
    text = get_text(user_id, 'top') + '\n\n' + '\n'.join(top_songs)
    await update.message.reply_text(text)

# Поиск музыки через API
async def search_music(query, limit=10):
    """Поиск музыки через Deezer API (бесплатный)"""
    try:
        url = f"https://api.deezer.com/search?q={query}&limit={limit}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []

# Скачивание музыки
async def download_music(track_url, track_id):
    """Скачивание превью трека (30 сек) через Deezer"""
    try:
        # Получаем информацию о треке
        response = requests.get(f"https://api.deezer.com/track/{track_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            preview_url = data.get('preview')
            
            if preview_url:
                # Скачиваем превью
                audio_response = requests.get(preview_url, timeout=30)
                if audio_response.status_code == 200:
                    return audio_response.content
        return None
    except Exception as e:
        logger.error(f"Download error: {e}")
        return None

# Обработка текстовых сообщений (поиск)
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text
    
    if not await check_subscription(update, context):
        keyboard = [[InlineKeyboardButton(get_text(user_id, 'check_sub'), callback_data='check_sub')]]
        await update.message.reply_text(get_text(user_id, 'subscribe'), reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    # Показываем статус поиска
    status_msg = await update.message.reply_text(get_text(user_id, 'searching').format(query))
    
    # Ищем музыку
    results = await search_music(query)
    
    if not results:
        await status_msg.edit_text(get_text(user_id, 'no_results').format(query))
        return
    
    # Сохраняем результаты в контекст
    context.user_data['search_results'] = results
    
    # Формируем сообщение с результатами
    text = get_text(user_id, 'found').format(len(results)) + '\n\n'
    
    for idx, track in enumerate(results[:10], 1):
        artist = track.get('artist', {}).get('name', 'Unknown')
        title = track.get('title', 'Unknown')
        text += f"{idx}. {artist} - {title}\n"
    
    text += '\n' + get_text(user_id, 'select')
    
    # Создаем клавиатуру с кнопками
    keyboard = []
    row = []
    for i in range(1, min(len(results) + 1, 11)):
        emoji_number = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟'][i-1]
        row.append(InlineKeyboardButton(emoji_number, callback_data=f'download_{i-1}'))
        
        if len(row) == 3:
            keyboard.append(row)
            row = []
    
    if row:
        keyboard.append(row)
    
    await status_msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# Обработка нажатий на кнопки
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    # Изменение языка
    if query.data.startswith('lang_'):
        lang = query.data.split('_')[1]
        user_settings[user_id] = {'lang': lang}
        await query.edit_message_text(get_text(user_id, 'lang_changed'))
        return
    
    # Проверка подписки
    if query.data == 'check_sub':
        if await check_subscription(update, context):
            await query.edit_message_text(get_text(user_id, 'subscribed'))
        else:
            await query.answer(get_text(user_id, 'subscribe'), show_alert=True)
        return
    
    # Скачивание трека
    if query.data.startswith('download_'):
        if not await check_subscription(update, context):
            keyboard = [[InlineKeyboardButton(get_text(user_id, 'check_sub'), callback_data='check_sub')]]
            await query.edit_message_text(get_text(user_id, 'subscribe'), reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        track_index = int(query.data.split('_')[1])
        results = context.user_data.get('search_results', [])
        
        if track_index < len(results):
            track = results[track_index]
            track_id = track.get('id')
            artist = track.get('artist', {}).get('name', 'Unknown')
            title = track.get('title', 'Unknown')
            
            await query.edit_message_text(get_text(user_id, 'downloading'))
            
            # Скачиваем трек
            audio_data = await download_music(track.get('link'), track_id)
            
            if audio_data:
                # Отправляем аудио
                await context.bot.send_audio(
                    chat_id=user_id,
                    audio=audio_data,
                    title=title,
                    performer=artist,
                    duration=30,
                    filename=f"{artist} - {title}.mp3"
                )
                await query.message.delete()
            else:
                await query.edit_message_text(get_text(user_id, 'error').format('Не удалось скачать трек'))

# Обработка ошибок
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")

def main():
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Создаем приложение бота
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CommandHandler("top", top_hits))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Bot started!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
