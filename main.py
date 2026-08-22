import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from config import BOT_TOKEN, ADMIN_ID, MAIN_CHANNEL_ID, BACKUP_CHANNEL_ID, MAIN_CHANNEL_LINK, BACKUP_CHANNEL_LINK, TARGET_CHANNEL_ID
from database import DatabaseManager

logging.basicConfig(level=logging.INFO)

# Conversation States
ASK_NAME, ASK_POSTER, ASK_LANGS, ASK_SEASONS, ASK_EPS, ASK_RATING, ASK_EP_IDS = range(7)
ASK_HELP_TEXT = 10

async def check_membership(bot, user_id: int) -> bool:
    try:
        m1 = await bot.get_chat_member(chat_id=MAIN_CHANNEL_ID, user_id=user_id)
        m2 = await bot.get_chat_member(chat_id=BACKUP_CHANNEL_ID, user_id=user_id)
        valid = ['member', 'administrator', 'creator']
        return m1.status in valid and m2.status in valid
    except Exception:
        return False

# --- User Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    DatabaseManager.register_user(user_id)
    
    if not await check_membership(context.bot, user_id):
        keyboard = [
            [InlineKeyboardButton("Join Main Channel", url=MAIN_CHANNEL_LINK)],
            [InlineKeyboardButton("Join Backup Channel", url=BACKUP_CHANNEL_LINK)],
            [InlineKeyboardButton("Check Again 🔄", callback_data="verify_join")]
        ]
        text = "⚠️ Please join both channels to use the bot:"
        if update.callback_query:
            await update.callback_query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    keyboard = [
        [InlineKeyboardButton("🔎 Search Anime", callback_data="user_search")],
        [InlineKeyboardButton("📂 Anime List", callback_data="user_list"), InlineKeyboardButton("ℹ️ Help", callback_data="user_help")]
    ]
    await update.message.reply_text(f"Welcome to the Anime Hub! Choose an option below or send an Anime name to search:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await check_membership(context.bot, user_id):
        await start_command(update, context)
        return

    query = update.message.text.strip()
    anime, suggestions = DatabaseManager.search_anime(query)

    if not anime:
        sug_text = "\n".join([f"• {s}" for s in suggestions]) if suggestions else "No suggestions found."
        await update.message.reply_text(f"❌ Anime not found!\n\nDid you mean:\n{sug_text}")
        return

    context.user_data['current_anime'] = anime
    
    try:
        await context.bot.copy_message(chat_id=user_id, from_chat_id=TARGET_CHANNEL_ID, message_id=anime['poster_msg_id'])
    except Exception:
        pass

    keyboard = []
    langs = anime.get('languages', [])
    if "Hindi" in langs: keyboard.append(InlineKeyboardButton("🇮🇳 Hindi", callback_data="ulang_Hindi"))
    if "English" in langs: keyboard.append(InlineKeyboardButton("🇬🇧 English", callback_data="ulang_English"))
    
    markup = InlineKeyboardMarkup([keyboard])
    await update.message.reply_text(f"🎬 *{anime['name']}*\n⭐ Rating: {anime.get('rating', 'N/A')}/10\n\nSelect Language:", parse_mode="Markdown", reply_markup=markup)

async def user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id

    if not data.startswith("admin_") and data != "verify_join" and not data.startswith("addlang_"):
        if not await check_membership(context.bot, user_id):
            await start_command(update, context)
            return

    if data == "verify_join":
        await start_command(update, context)
    
    elif data == "user_search":
        await query.message.reply_text("🔎 Type and send the Anime name in the chat.")
    
    elif data == "user_help":
        help_text = DatabaseManager.get_help_text()
        await query.message.reply_text(f"ℹ️ *Help & Support*\n\n{help_text}", parse_mode="Markdown")
        
    elif data == "user_list":
        animes = DatabaseManager.get_all_animes()
        if not animes:
            await query.message.reply_text("List is empty.")
            return
        text = "📂 *Available Animes:*\n\n"
        for a in animes:
            text += f"• *{a['name']}* - {a.get('seasons', 1)} Seasons, {a.get('total_episodes', 0)} Eps (⭐ {a.get('rating', 'N/A')})\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data.startswith("ulang_"):
        lang = data.split("_")[1]
        context.user_data['sel_lang'] = lang
        anime = context.user_data.get('current_anime')
        seasons = anime.get('seasons', 1)
        keyboard = [[InlineKeyboardButton(f"Season {s}", callback_data=f"useason_{s}")] for s in range(1, seasons + 1)]
        await query.edit_message_text(f"Language: *{lang}*\n\nSelect Season:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("useason_"):
        season = data.split("_")[1]
        context.user_data['sel_season'] = season
        anime = context.user_data.get('current_anime')
        total_eps = anime.get('total_episodes', 12)
        
        keyboard, row = [], []
        for ep in range(1, total_eps + 1):
            row.append(InlineKeyboardButton(f"Ep {ep}", callback_data=f"uep_{ep}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row: keyboard.append(row)
        await query.edit_message_text(f"Season {season} | {context.user_data.get('sel_lang')}\n\nSelect Episode:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("uep_"):
        ep_num = data.split("_")[1]
        season = context.user_data.get('sel_season')
        lang = context.user_data.get('sel_lang')
        anime = context.user_data.get('current_anime')
        
        # Auto-Delete previous video
        last_vid = context.user_data.get('last_video_msg_id')
        if last_vid:
            try:
                await context.bot.delete_message(chat_id=user_id, message_id=last_vid)
            except Exception:
                pass

        ep_msg_id = DatabaseManager.get_episode_msg_id(anime['key'], season, ep_num, lang)
        if ep_msg_id:
            try:
                msg = await context.bot.copy_message(chat_id=user_id, from_chat_id=TARGET_CHANNEL_ID, message_id=ep_msg_id)
                context.user_data['last_video_msg_id'] = msg.message_id
            except Exception:
                await query.answer("Error forwarding video. Please check channel permissions.", show_alert=True)
        else:
            await query.answer("Episode not found in database.", show_alert=True)

# --- Admin Core ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    total = DatabaseManager.get_total_users()
    keyboard = [
        [InlineKeyboardButton("➕ Add Anime", callback_data="admin_add"), InlineKeyboardButton("🗑️ Delete Content", callback_data="admin_del")],
        [InlineKeyboardButton("📜 Manage List", callback_data="user_list"), InlineKeyboardButton("ℹ️ Edit Help", callback_data="admin_edit_help")]
    ]
    await update.message.reply_text(f"🛠️ *Admin Dashboard*\nTotal Users: {total}", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Admin: Add Anime Flow ---
async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Send the Anime Name/Key (e.g., Naruto):\nType /cancel to abort.")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_name'] = update.message.text.strip()
    await update.message.reply_text("Send the Private Channel Message ID of the Poster:")
    return ASK_POSTER

async def ask_poster(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_poster'] = int(update.message.text.strip())
    keyboard = [
        [InlineKeyboardButton("Add Hindi", callback_data="addlang_Hindi"), InlineKeyboardButton("Add English", callback_data="addlang_English")],
        [InlineKeyboardButton("Done ✅", callback_data="addlang_done")]
    ]
    context.user_data['add_langs'] = []
    await update.message.reply_text("Select available languages:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_LANGS

async def handle_add_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if data == "addlang_done":
        await query.message.reply_text("How many Seasons does it have? (Send a number):")
        return ASK_SEASONS
    else:
        lang = data.split("_")[1]
        if lang not in context.user_data['add_langs']:
            context.user_data['add_langs'].append(lang)
            await query.answer(f"{lang} added!")
        return ASK_LANGS

async def ask_seasons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_seasons'] = int(update.message.text.strip())
    await update.message.reply_text("How many total Episodes per season? (Send a number):")
    return ASK_EPS

async def ask_eps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_total_eps'] = int(update.message.text.strip())
    await update.message.reply_text("What is the Rating? (e.g., 8.5):")
    return ASK_RATING

async def ask_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['add_rating'] = float(update.message.text.strip())
    
    # Save basic Anime data
    DatabaseManager.add_anime_data(context.user_data['add_name'], {
        'name': context.user_data['add_name'],
        'poster_msg_id': context.user_data['add_poster'],
        'languages': context.user_data['add_langs'],
        'seasons': context.user_data['add_seasons'],
        'total_episodes': context.user_data['add_total_eps'],
        'rating': context.user_data['add_rating']
    })
    
    # Setup loop for IDs
    context.user_data['current_ep_setup'] = 1
    lang_str = context.user_data['add_langs'][0] if context.user_data['add_langs'] else "Unknown"
    context.user_data['setup_lang'] = lang_str
    
    await update.message.reply_text(f"Anime profile saved!\nNow, let's map Video IDs.\nSend Message ID for Season 1 - Episode 1 ({lang_str}):")
    return ASK_EP_IDS

async def ask_ep_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ep = context.user_data['current_ep_setup']
    msg_id = int(update.message.text.strip())
    
    DatabaseManager.save_episode_mapping(
        context.user_data['add_name'], 1, ep, context.user_data['setup_lang'], msg_id
    )
    
    ep += 1
    if ep > context.user_data['add_total_eps']:
        await update.message.reply_text("✅ All episodes mapped successfully! Setup complete.")
        return ConversationHandler.END
    else:
        context.user_data['current_ep_setup'] = ep
        await update.message.reply_text(f"Send Message ID for Season 1 - Episode {ep} ({context.user_data['setup_lang']}):")
        return ASK_EP_IDS

# --- Admin: Delete Flow ---
async def admin_del_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    animes = DatabaseManager.get_all_animes()
    keyboard = [[InlineKeyboardButton(a['name'], callback_data=f"del1_{a['key']}")] for a in animes]
    await update.callback_query.message.reply_text("Select Anime to Manage/Delete:", reply_markup=InlineKeyboardMarkup(keyboard))

async def del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data.startswith("del1_"):
        key = data.split("_")[1]
        keyboard = [
            [InlineKeyboardButton("🇮🇳 Delete Hindi", callback_data=f"del2_{key}_Hindi")],
            [InlineKeyboardButton("🇬🇧 Delete English", callback_data=f"del2_{key}_English")],
            [InlineKeyboardButton("❌ Delete Entire Anime", callback_data=f"del_all_{key}")]
        ]
        await query.edit_message_text(f"Manage deletion for {key}:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("del_all_"):
        key = data.split("_")[2]
        DatabaseManager.delete_entire_anime(key)
        await query.edit_message_text(f"✅ {key} has been completely deleted.")
        
    elif data.startswith("del2_"):
        parts = data.split("_")
        key, lang = parts[1], parts[2]
        keyboard = [
            [InlineKeyboardButton(f"🗑️ Delete All {lang} Episodes", callback_data=f"del_langall_{key}_{lang}")],
            [InlineKeyboardButton("🗑️ Delete Specific Episode", callback_data=f"del3_{key}_{lang}")]
        ]
        await query.edit_message_text(f"Language: {lang}\nChoose action:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("del_langall_"):
        parts = data.split("_")
        key, lang = parts[2], parts[3]
        DatabaseManager.delete_language_data(key, lang)
        await query.edit_message_text(f"✅ {lang} data for {key} deleted.")
        
    elif data.startswith("del3_"):
        parts = data.split("_")
        key, lang = parts[1], parts[2]
        # Allow deleting up to Ep 10 for simplicity in inline menu
        keyboard = [[InlineKeyboardButton(f"Ep {i}", callback_data=f"del4_{key}_{lang}_1_{i}")] for i in range(1, 11)]
        await query.edit_message_text("Select Episode to Delete:", reply_markup=InlineKeyboardMarkup(keyboard))
        
    elif data.startswith("del4_"):
        parts = data.split("_")
        key, lang, season, ep = parts[1], parts[2], parts[3], parts[4]
        DatabaseManager.delete_single_episode(key, season, ep, lang)
        await query.edit_message_text(f"✅ Season {season} Ep {ep} ({lang}) deleted.")

# --- Admin: Edit Help Flow ---
async def admin_help_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("Send the new Help Text / Support ID (or /cancel to abort):")
    return ASK_HELP_TEXT

async def save_help_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    DatabaseManager.set_help_text(text)
    await update.message.reply_text("✅ Help info updated successfully!")
    return ConversationHandler.END

async def cancel_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Process cancelled.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_start, pattern="^admin_add$")],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
            ASK_POSTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_poster)],
            ASK_LANGS: [CallbackQueryHandler(handle_add_lang, pattern="^addlang_")],
            ASK_SEASONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_seasons)],
            ASK_EPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_eps)],
            ASK_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_rating)],
            ASK_EP_IDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_ep_ids)],
        },
        fallbacks=[CommandHandler("cancel", cancel_setup)]
    )

    help_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_help_start, pattern="^admin_edit_help$")],
        states={ASK_HELP_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_help_text)]},
        fallbacks=[CommandHandler("cancel", cancel_setup)]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    
    app.add_handler(add_conv)
    app.add_handler(help_conv)
    
    app.add_handler(CallbackQueryHandler(del_callback, pattern="^del"))
    app.add_handler(CallbackQueryHandler(user_callback))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("Bot is up and running...")
    app.run_polling()

if __name__ == '__main__':
    main()
