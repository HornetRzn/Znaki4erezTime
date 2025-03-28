import os
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    InputMediaPhoto,
    InputMediaVideo
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
)
from dotenv import load_dotenv
import sqlite3
from datetime import datetime

# Загрузка токена из .env
load_dotenv()

# Настройка базы данных
conn = sqlite3.connect('dating.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        age INTEGER,
        orientation TEXT,
        role TEXT,
        location TEXT,
        bio TEXT,
        photos TEXT,
        video TEXT,
        state TEXT,
        current_match INTEGER,
        message_count INTEGER DEFAULT 0
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        match_id INTEGER PRIMARY KEY,
        user1 INTEGER,
        user2 INTEGER,
        user1_liked BOOLEAN,
        user2_liked BOOLEAN,
        chat_active BOOLEAN,
        messages_exchanged INTEGER
    )
''')
conn.commit()

# Состояния разговора
(
    NAME,
    AGE,
    ORIENTATION,
    ROLE,
    LOCATION,
    BIO,
    PHOTOS,
    MAIN_MENU,
    VIEW_PROFILES,
    CHATTING,
) = range(10)

# Настройка логгирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user.id,))
    if cursor.fetchone() is None:
        await update.message.reply_text("Привет! Давай создадим твой профиль.\nКак тебя зовут?")
        return NAME
    else:
        await show_main_menu(update, context)
        return MAIN_MENU

async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Сколько тебе лет?")
    return AGE

async def process_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['age'] = update.message.text
    reply_keyboard = [["Гей", "Би", "Транс", "Гетеро", "Другое"]]
    await update.message.reply_text(
        "Твоя сексуальная ориентация:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True, resize_keyboard=True),
    )
    return ORIENTATION

async def process_orientation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['orientation'] = update.message.text
    await update.message.reply_text("Твоя роль в сексе:")
    return ROLE

async def process_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['role'] = update.message.text
    await update.message.reply_text("В каком районе Рязани (области) ты живёшь?")
    return LOCATION

async def process_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['location'] = update.message.text
    await update.message.reply_text("Расскажи о себе, кого хочешь найти?")
    return BIO

async def process_bio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['bio'] = update.message.text
    await update.message.reply_text("Прикрепи от 1 до 3 фотографий или видео (15 сек). Нажми /done чтобы закончить.")
    return PHOTOS

async def process_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []
    
    if update.message.photo:
        photo = update.message.photo[-1].file_id
        context.user_data['photos'].append(photo)
    elif update.message.video:
        context.user_data['video'] = update.message.video.file_id
    
    if len(context.user_data['photos']) >= 3:
        await finish_profile(update, context)
        return MAIN_MENU
    else:
        return PHOTOS

async def finish_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_data = context.user_data
    photos = ','.join(user_data.get('photos', []))
    video = user_data.get('video', '')
    
    cursor.execute('''
        INSERT OR REPLACE INTO users 
        (user_id, name, age, orientation, role, location, bio, photos, video, state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        update.message.from_user.id,
        user_data['name'],
        user_data['age'],
        user_data['orientation'],
        user_data['role'],
        user_data['location'],
        user_data['bio'],
        photos,
        video,
        'active'
    ))
    conn.commit()
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("Смотреть анкеты", callback_data='view_profiles')],
        [InlineKeyboardButton("Мой профиль", callback_data='my_profile')]
    ]
    await update.message.reply_text("Главное меню:", reply_markup=InlineKeyboardMarkup(keyboard))
    return MAIN_MENU

async def view_profiles(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    cursor.execute('''
        SELECT * FROM users 
        WHERE user_id != ? 
        AND orientation IN (SELECT orientation FROM users WHERE user_id = ?)
        ORDER BY RANDOM() LIMIT 1
    ''', (user_id, user_id))
    profile = cursor.fetchone()
    
    if not profile:
        await query.message.reply_text("Анкет пока нет. Попробуйте позже.")
        return MAIN_MENU
    
    context.user_data['current_profile'] = profile[0]
    media = []
    photos = profile[7].split(',') if profile[7] else []
    for photo in photos[:3]:
        media.append(InputMediaPhoto(photo))
    if profile[8]:
        media.append(InputMediaVideo(profile[8]))
    
    await query.message.reply_media_group(media=media)
    text = f"""
    Имя: {profile[1]}
    Возраст: {profile[2]}
    Ориентация: {profile[3]}
    Роль: {profile[4]}
    Район: {profile[5]}
    О себе: {profile[6]}
    """
    keyboard = [[InlineKeyboardButton("❤️", callback_data='like'), InlineKeyboardButton("👎", callback_data='dislike')]]
    await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return VIEW_PROFILES

async def handle_like(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    liked_user = context.user_data['current_profile']
    
    cursor.execute('''
        SELECT * FROM matches 
        WHERE (user1 = ? AND user2 = ?) OR (user1 = ? AND user2 = ?)
    ''', (user_id, liked_user, liked_user, user_id))
    match = cursor.fetchone()
    
    if match:
        cursor.execute('''
            UPDATE matches SET 
            user1_liked = CASE WHEN user1 = ? THEN TRUE ELSE user1_liked END,
            user2_liked = CASE WHEN user2 = ? THEN TRUE ELSE user2_liked END,
            chat_active = TRUE
            WHERE match_id = ?
        ''', (user_id, user_id, match[0]))
    else:
        cursor.execute('''
            INSERT INTO matches (user1, user2, user1_liked, user2_liked, chat_active, messages_exchanged)
            VALUES (?, ?, TRUE, FALSE, FALSE, 0)
        ''', (user_id, liked_user))
    
    conn.commit()
    
    if match and match[3] and match[4]:
        await start_chat(user_id, liked_user, context)
    
    return await view_profiles(update, context)

async def start_chat(user1: int, user2: int, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(user1, "🎉 У вас новый мэтч! Начинайте общение (осталось 5 сообщений).")
    await context.bot.send_message(user2, "🎉 У вас новый мэтч! Начинайте общение (осталось 5 сообщений).")
    cursor.execute('UPDATE users SET current_match = ?, message_count = 0 WHERE user_id IN (?, ?)', (user2, user1, user2))
    conn.commit()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.message.from_user
    cursor.execute('SELECT current_match, message_count FROM users WHERE user_id = ?', (user.id,))
    data = cursor.fetchone()
    
    if data and data[0]:
        match_user, count = data[0], data[1]
        if count >= 5:
            await update.message.reply_text("🚫 Лимит сообщений исчерпан!")
            return
        
        await context.bot.send_message(match_user, f"💬 Анонимное сообщение ({5 - count} осталось):\n{update.message.text}")
        cursor.execute('UPDATE users SET message_count = message_count + 1 WHERE user_id = ?', (user.id,))
        conn.commit()
        
        cursor.execute('SELECT message_count FROM users WHERE user_id = ?', (match_user,))
        other_count = cursor.fetchone()[0]
        if count + 1 >= 5 and other_count >= 5:
            await offer_contact_exchange(user.id, match_user, context)

async def offer_contact_exchange(user1: int, user2: int, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("ДА", callback_data='share_contact')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(user1, "🤝 Кажется, вы созрели для обмена контактами!", reply_markup=reply_markup)
    await context.bot.send_message(user2, "🤝 Кажется, вы созрели для обмена контактами!", reply_markup=reply_markup)

async def handle_contact_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    if query.data == 'share_contact':
        cursor.execute('SELECT current_match FROM users WHERE user_id = ?', (user.id,))
        match_user = cursor.fetchone()[0]
        await context.bot.send_message(match_user, f"📲 Ваш собеседник согласился поделиться контактом: @{user.username}")
    else:
        await query.message.reply_text("❌ Хорошо, удачи в поисках!")
    
    cursor.execute('UPDATE users SET current_match = NULL, message_count = 0 WHERE user_id = ?', (user.id,))
    conn.commit()

def main() -> None:
    application = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_age)],
            ORIENTATION: [MessageHandler(filters.Regex(r"^(Гей|Би|Транс|Гетеро|Другое)$"), process_orientation)],
            ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_role)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_location)],
            BIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_bio)],
            PHOTOS: [
                MessageHandler(filters.PHOTO | filters.VIDEO, process_photos),
                CommandHandler("done", finish_profile)
            ],
            MAIN_MENU: [CallbackQueryHandler(view_profiles, pattern='^view_profiles$')],
            VIEW_PROFILES: [
                CallbackQueryHandler(handle_like, pattern='^like$'),
                CallbackQueryHandler(view_profiles, pattern='^dislike$')
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_contact_decision, pattern='^share_contact$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.run_polling()

if __name__ == "__main__":
    main()
