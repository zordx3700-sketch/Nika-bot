import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from config import BOT_TOKEN, ADMIN_ID, MAIN_CHANNEL_ID, BACKUP_CHANNEL_ID, MAIN_CHANNEL_LINK, BACKUP_CHANNEL_LINK, CHANNEL_MAP
from database import DatabaseManager

logging.basicConfig(level=logging.INFO)

async def check_membership(bot, user_id: int) -> bool:
    try:
        m1 = await bot.get_chat_member(chat_id=MAIN_CHANNEL_ID, user_id=user_id)
        m2 = await bot.get_chat_member(chat_id=BACKUP_CHANNEL_ID, user_id=user_id)
        return m1.status in ['member', 'administrator', 'creator'] and m2.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    DatabaseManager.register_user(user.id, user.username, user.first_name)
    
    if not await check_membership(context.bot, user.id):
        keyboard = [
            [InlineKeyboardButton("Join Main Channel", url=MAIN_CHANNEL_LINK)],
            [InlineKeyboardButton("Join Backup Channel", url=BACKUP_CHANNEL_LINK)],
            [InlineKeyboardButton("Check Again 🔄", callback_data="verify_join")]
        ]
        await update.message.reply_text("⚠️ Join both channels to use this bot:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    await update.message.reply_text(f"Welcome {user.first_name}! Send any Anime Name (e.g. Naruto) to search.")

# --- Search Flow ---
async def handle_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_membership(context.bot, user_id):
        await start_command(update, context)
        return

    query = update.message.text.strip()
    anime, suggestions = DatabaseManager.search_anime(query)

    if not anime:
        sug_text = "\n".join([f"• {s}" for s in suggestions]) if suggestions else "No suggestions."
        await update.message.reply_text(f"❌ Anime not found!\n\nDid you mean:\n{sug_text}")
        return

    context.user_data['anime'] = anime
    
    # Step 1: Language First
    keyboard = []
    if "Hindi" in anime.get('languages', []):
        keyboard.append(InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi"))
    if "English" in anime.get('languages', []):
        keyboard.append(InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"))
    
    markup = InlineKeyboardMarkup([keyboard])
    caption = f"🎬 *{anime['name']}*\n⭐ Rating: {anime['rating']}/10\n📺 Total Seasons: {anime['seasons']}\n\nSelect Language:"

    if anime.get('poster_url'):
        await update.message.reply_photo(photo=anime['poster_url'], caption=caption, parse_mode="Markdown", reply_markup=markup)
    else:
        await update.message.reply_text(caption, parse_mode="Markdown", reply_markup=markup)

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "verify_join":
        if await check_membership(context.bot, user_id):
            await query.message.reply_text("✅ Membership verified! Type anime name to search.")
        return

    anime = context.user_data.get('anime')

    # Step 2: Language Clicked -> Show Seasons
    if data.startswith("lang_"):
        lang = data.split("_")[1]
        context.user_data['lang'] = lang
        seasons = anime.get('seasons', 1)
        keyboard = [[InlineKeyboardButton(f"Season {s}", callback_data=f"season_{s}")] for s in range(1, seasons + 1)]
        await query.edit_message_caption(caption=f"Selected Language: *{lang}*\n\nSelect Season:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    # Step 3: Season Clicked -> Show Episodes
    elif data.startswith("season_"):
        season = data.split("_")[1]
        context.user_data['season'] = season
        total_eps = anime.get('total_episodes', 12)
        
        keyboard, row = [], []
        for ep in range(1, total_eps + 1):
            row.append(InlineKeyboardButton(f"Ep {ep}", callback_data=f"ep_{ep}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)

        await query.edit_message_caption(caption=f"Season {season} | Language: {context.user_data.get('lang')}\n\nSelect Episode:", reply_markup=InlineKeyboardMarkup(keyboard))

    # Step 4: Episode Clicked -> Auto Delete Previous & Forward New Video
    elif data.startswith("ep_"):
        ep_num = data.split("_")[1]
        
        # Delete previous video if exists
        last_vid_id = context.user_data.get('last_video_msg_id')
        if last_vid_id:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=last_vid_id)
            except Exception:
                pass

        # Send new video (Fetching from private channel target map)
        ch_id = CHANNEL_MAP.get("720p_Hindi") # Example Channel
        try:
            # forwarding logic using telegram message id mapping
            msg = await context.bot.send_message(chat_id=user_id, text=f"📽️ Sending *{anime['name']}* S{context.user_data.get('season')} Ep {ep_num}...", parse_mode="Markdown")
            context.user_data['last_video_msg_id'] = msg.message_id
        except Exception as e:
            await query.message.reply_text(f"Error fetching episode: {e}")

# --- Admin Panel Commands ---
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    total_users = DatabaseManager.get_total_users()
    text = (
        f"🛠️ *Admin Panel*\n\n"
        f"👤 Total Bot Users: `{total_users}`\n\n"
        f"*Commands:*\n"
        f"• `/addanime id|name|seasons|eps|Hindi,English|rating|poster_url|keywords`\n"
        f"• `/delanime anime_id`"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def add_anime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    try:
        raw = " ".join(context.args).split("|")
        DatabaseManager.add_anime(raw[0].strip(), raw[1].strip(), raw[2].strip(), raw[3].strip(), raw[4].strip().split(","), raw[5].strip(), raw[6].strip(), raw[7].strip())
        await update.message.reply_text("✅ Anime Added Successfully!")
    except Exception as e:
        await update.message.reply_text(f"❌ Syntax Error. Example:\n`/addanime naruto|Naruto Shippuden|2|500|Hindi,English|8.7|https://image.link|naruto,shippuden`")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("addanime", add_anime_command))
    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.run_polling()

if __name__ == '__main__':
    main()
