import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, CallbackQueryHandler, filters
)

# ========================
# CONFIGURATION
# ========================
import os
BOT_TOKEN = os.getenv("BOT_TOKEN","7984690320:AAE-27oCNYE0IX8ylg0Z0Z9k7_-kYdST06s")  # replace with your token
ALLOWED_CREATORS = {5982449237, 987654321, 5932446309, 5912536321}  # replace with Telegram user IDs

# group_games: each group can have its own game
group_games = {}

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# ========================
# HELPERS
# ========================
async def show_numbers(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id=None):
    """Show available numbers in group."""
    if chat_id is None:
        chat_id = update.effective_chat.id

    game = group_games[chat_id]
    max_players = game["max_players"]
    picks = game["picks"]

    keyboard, row = [], []
    for i in range(1, max_players + 1):
        if i not in picks:  # only show available numbers
            row.append(InlineKeyboardButton(str(i), callback_data=f"pick_{i}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text="📋 Available numbers:",
        reply_markup=reply_markup
    )


# ========================
# COMMAND HANDLERS
# ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if user_id not in ALLOWED_CREATORS:
        await update.message.reply_text("⚠️ You are not allowed to start a new game in this group.")
        return

    # Initialize game for this group
    group_games[chat_id] = {
        "creator": user_id,
        "picks": {},
        "max_players": 0,
        "num_winners": 0
    }

    await update.message.reply_text(
        f"🎲 {update.effective_user.first_name} started a new lottery game!\n"
        "👉 First, tell me how many players? (send a number)"
    )
    context.user_data["waiting_for"] = "max_players"


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    text = update.message.text

    if chat_id not in group_games:
        return  # no game in this group

    game = group_games[chat_id]

    # Only game creator can configure
    if game["creator"] != user_id:
        return

    if context.user_data.get("waiting_for") == "max_players":
        try:
            n = int(text)
            if n < 1:
                await update.message.reply_text("⚠️ Must be at least 1 player.")
                return
            game["max_players"] = n
            context.user_data["waiting_for"] = "num_winners"
            await update.message.reply_text(f"✅ Max players set to {n}\n👉 Now send number of winners:")
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid number.")

    elif context.user_data.get("waiting_for") == "num_winners":
        try:
            n = int(text)
            if n < 1:
                await update.message.reply_text("⚠️ Must be at least 1 winner.")
                return
            game["num_winners"] = n
            context.user_data["waiting_for"] = None
            await update.message.reply_text(
                f"✅ Number of winners set to {n}\n\n"
                "👉 Players can now pick numbers!"
            )
            await show_numbers(update, context, chat_id)
        except ValueError:
            await update.message.reply_text("⚠️ Please enter a valid number.")


# Player picks a number
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    user = query.from_user.first_name
    user_id = query.from_user.id

    if chat_id not in group_games:
        await query.answer("⚠️ No active game in this group.", show_alert=True)
        return

    game = group_games[chat_id]
    data = query.data

    if data.startswith("pick_"):
        number = int(data.split("_")[1])
        picks = game["picks"]

        if number in picks:
            await query.answer(f"❌ Number {number} already taken by {picks[number]}", show_alert=True)
        else:
            picks[number] = user
            await query.answer(f"✅ You picked {number}!", show_alert=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"✅ {user} picked number {number}"
            )

        # Refresh board
        await show_numbers(update, context, chat_id)


# /list - only creator
async def list_picks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id not in group_games:
        await update.message.reply_text("⚠️ No game running here.")
        return

    game = group_games[chat_id]
    if game["creator"] != user_id:
        await update.message.reply_text("⚠️ Only the game creator can use this command.")
        return

    picks = game["picks"]
    if not picks:
        await update.message.reply_text("📋 No numbers picked yet.")
        return

    # Group picks by user
    players = {}
    for num, u in sorted(picks.items()):
        players.setdefault(u, []).append(num)

    text = "📋 Current picks:\n"
    for player, nums in players.items():
        text += f"{player} → {', '.join(map(str, nums))}\n"

    await update.message.reply_text(text)


# /draw - only creator
async def draw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if chat_id not in group_games:
        await update.message.reply_text("⚠️ No game running here.")
        return

    game = group_games[chat_id]
    if game["creator"] != user_id:
        await update.message.reply_text("⚠️ Only the game creator can use this command.")
        return

    picks = game["picks"]
    if not picks:
        await update.message.reply_text("⚠️ No picks made yet.")
        return

    chosen_numbers = random.sample(
        list(picks.keys()),
        min(game["num_winners"], len(picks))
    )
    winners = [f"{num} → {picks[num]}" for num in chosen_numbers]

    await update.message.reply_text(
        f"🎉 Drawing {game['num_winners']} winner(s)...\n\n" + "\n".join(winners)
    )
# /remove <number>  –  player can remove their own pick; creator can remove any
async def remove_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    if chat_id not in group_games:
        await update.message.reply_text("⚠️ No game running here.")
        return

    game = group_games[chat_id]
    picks = game["picks"]

    # Validate argument
    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /remove <number>")
        return

    number = int(context.args[0])

    if number not in picks:
        await update.message.reply_text(f"⚠️ Number {number} isn’t picked.")
        return

    # Allow only the original picker or the creator
    if picks[number] != user_name and game["creator"] != user_id:
        await update.message.reply_text(
            "⚠️ Only the person who picked it or the game creator can remove this number."
        )
        return

    del picks[number]
    await update.message.reply_text(f"✅ Number {number} has been released.")
    await show_numbers(update, context, chat_id)


# ========================
# MAIN
# ========================
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_picks))
    app.add_handler(CommandHandler("draw", draw))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("remove", remove_pick))

    print("🤖 Bot is running...")
    app.run_polling()
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()


if __name__ == "__main__":
    main()
