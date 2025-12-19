import json
import os
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Data file
DATA_FILE = "./data/pool_data.json"
load_dotenv()
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# Load data
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"players": [], "games": []}

# Save data
def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎯 Add Player", callback_data="add_player")],
        [InlineKeyboardButton("📊 Add Game Result", callback_data="add_game")],
        [InlineKeyboardButton("📈 Show Stats", callback_data="show_stats")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Welcome to Pool Match Tracker! Choose an option:", reply_markup=reply_markup)

# Handle button clicks
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "add_player":
        await query.edit_message_text("Send the name of the new player.")
        context.user_data["awaiting"] = "add_player"

    elif query.data == "add_game":
        data = load_data()
        if len(data["players"]) < 2:
            await query.edit_message_text("You need at least 2 players to record a game.")
            return
        context.user_data["awaiting"] = "add_game_winner"
        await query.edit_message_text("Send the winner’s name.")

    elif query.data == "show_stats":
        await show_general_stats(update, context)

# Add player
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    data = load_data()

    if context.user_data.get("awaiting") == "add_player":
        if text in data["players"]:
            await update.message.reply_text(f"Player '{text}' already exists!")
        else:
            data["players"].append(text)
            save_data(data)
            await update.message.reply_text(f"✅ Player '{text}' added!")
        context.user_data.pop("awaiting", None)
        await start(update, context)

    elif context.user_data.get("awaiting") == "add_game_winner":
        context.user_data["winner"] = text
        context.user_data["awaiting"] = "add_game_loser"
        await update.message.reply_text("Now send the loser’s name.")

    elif context.user_data.get("awaiting") == "add_game_loser":
        winner = context.user_data.get("winner")
        loser = text
        if winner == loser:
            await update.message.reply_text("Winner and loser must be different!")
            return

        if winner not in data["players"] or loser not in data["players"]:
            await update.message.reply_text("One of the players does not exist! Use /start to add players.")
            return

        # Record game
        data["games"].append({"winner": winner, "loser": loser})
        save_data(data)
        await update.message.reply_text(f"✅ Game recorded: {winner} beat {loser}")
        context.user_data.pop("awaiting", None)
        await start(update, context)

# Show general stats
async def show_general_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    games = data["games"]
    if not games:
        await update.callback_query.edit_message_text("No games played yet.")
        return

    wins = {}
    for game in games:
        winner = game["winner"]
        loser = game["loser"]
        wins[winner] = wins.get(winner, 0) + 1
        wins[loser] = wins.get(loser, 0)

    total_games = len(games)
    win_rate = {p: (wins[p] / total_games) * 100 for p in wins}
    top_player = max(wins, key=wins.get)

    message = (
        f"📊 *General Stats*\n\n"
        f"Total games played: {total_games}\n"
        f"Top player: *{top_player}* ({wins[top_player]} wins)\n"
        f"Best win rate: {top_player} ({win_rate[top_player]:.1f}%)"
    )

    keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="start")]]
    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    # Add player vs player buttons
    await show_pvp_menu(update, context)

# Show player vs player selection
async def show_pvp_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    players = sorted(data["players"])
    buttons = []
    for i, p1 in enumerate(players):
        for p2 in players[i+1:]:
            btn = InlineKeyboardButton(f"{p1} vs {p2}", callback_data=f"pvp:{p1}:{p2}")
            buttons.append([btn])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="start")])
    reply_markup = InlineKeyboardMarkup(buttons)
    if update.callback_query and update.callback_query.message.text.startswith("📊 *General Stats*"):
        await update.callback_query.message.reply_text("🎯 *Head-to-Head Stats*", reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text("🎯 *Head-to-Head Stats*", reply_markup=reply_markup, parse_mode="Markdown")

# Show player vs player stats
async def show_pvp_stats(update: Update, context: ContextTypes.DEFAULT_TYPE, p1: str, p2: str):
    data = load_data()
    games = data["games"]

    p1_wins = sum(1 for g in games if g["winner"] == p1 and g["loser"] == p2)
    p2_wins = sum(1 for g in games if g["winner"] == p2 and g["loser"] == p1)
    total = p1_wins + p2_wins

    if total == 0:
        result = "No games between them."
    else:
        p1_rate = (p1_wins / total) * 100
        p2_rate = (p2_wins / total) * 100
        result = (
            f"{p1}: {p1_wins}W ({p1_rate:.1f}%)\n"
            f"{p2}: {p2_wins}W ({p2_rate:.1f}%)"
        )

    message = f"⚔️ *{p1} vs {p2}*\n\nGames played: {total}\n{result}"

    keyboard = [[InlineKeyboardButton("🔙 Back to Stats", callback_data="show_stats")]]
    await update.callback_query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

# Main
def main():
    app = Application.builder().token(BOT_TOKEN).build()  # ← Replace with your token

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CallbackQueryHandler(show_general_stats, pattern="show_stats"))
    app.add_handler(CallbackQueryHandler(start, pattern="start"))
    app.add_handler(CallbackQueryHandler(show_pvp_stats, pattern=r"^pvp:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running... Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
