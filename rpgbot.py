import logging
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from better_profanity import profanity
import random
import nest_asyncio

# Применение nest_asyncio для работы с вложенными event loop
nest_asyncio.apply()

# Initialize profanity filter with custom blacklist
profanity.load_censor_words(custom_words=['hitler', 'slur1', 'slur2'])
TOKEN = "7090445058:AAH9MShRuyAM1eJOJh5GmkzvYYokG_0rO1U"

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLite database setup  check_same_thread=False
conn = sqlite3.connect('game_bot.db')
cursor = conn.cursor()

# Create tables if they don't exist
cursor.execute(''' 
CREATE TABLE IF NOT EXISTS CharacterCreationRequests ( 
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    character_name TEXT, 
    flagged BOOLEAN DEFAULT 0 
) 
''')
cursor.execute(''' 
CREATE TABLE IF NOT EXISTS Characters ( 
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    name TEXT, 
    hp INTEGER, 
    attack INTEGER, 
    tier TEXT, 
    mana INTEGER, 
    speed INTEGER 
) 
''')
cursor.execute(''' 
CREATE TABLE IF NOT EXISTS Cases ( 
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    character_id INTEGER 
) 
''')
conn.commit()



# Command: /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Welcome to the RPG Bot! Here are the available commands:\n"
        "/create_character - Submit a character for admin approval.\n"
        "/review_characters - Admins can review character submissions.\n"
        "/my_characters - View your owned characters.\n"
        "/open_case - Open a gacha case to get a character.\n"
        "/pvp - Fight another player!\n"
        "/tips - Get tips about the game."
    )



async def create_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 6:
        await update.message.reply_text("Usage: /create_character <character_name> <tier> <hp> <attack> <mana> <speed>")
        return

    user_id = update.message.from_user.id
    character_name = context.args[0]
    tier = context.args[1]
    hp = int(context.args[2])
    attack = int(context.args[3])
    mana = int(context.args[4])
    speed = int(context.args[5])

    # Check for profanity
    is_flagged = profanity.contains_profanity(character_name)

   

    # Save to database
    cursor.execute(
        "INSERT INTO CharacterCreationRequests (user_id, character_name, flagged) VALUES (?, ?, ?)",
        (user_id, character_name, is_flagged)
    )
    conn.commit()

    if is_flagged:
        await update.message.reply_text(
            f"Your character name '{character_name}' has been submitted but was flagged for review. Admins will review it soon."
        )
    else:
        # Save the character in the 'Characters' table if no flag
        cursor.execute(
            "INSERT INTO Characters (user_id, name, hp, attack, tier, mana, speed) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, character_name, hp, attack, tier, mana, speed)
        )
        conn.commit()

        await update.message.reply_text(
            f"Your character '{character_name}' with tier '{tier}' has been successfully created:\n"
            f"HP: {hp}, Attack: {attack}, Mana: {mana}, Speed: {speed}"
        )

    conn.close()

# Command: /review_characters (Admin only)
async def review_characters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.message.from_user.username

    # Проверка, что администратор — это @shinbuu
    if username != "shinbuu":
        await update.message.reply_text("Only admins can review character submissions.")
        return

    cursor.execute("SELECT * FROM CharacterCreationRequests")
    results = cursor.fetchall()

    if not results:
        await update.message.reply_text("No pending character submissions.")
        return

    message = "Pending Character Submissions:\n"
    for row in results:
        char_id, user_id, character_name, flagged = row
        warning = " (⚠️ FLAGGED)" if flagged else ""
        message += f"ID: {char_id}, Name: {character_name}{warning}\n"

    await update.message.reply_text(message)

    # Adding option to approve or reject character creation
    await update.message.reply_text("To approve a character, type: /approve_character <id>.\n"
                                    "To reject a character, type: /reject_character <id>.")

# Command: /approve_character (Admin only)
async def approve_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.message.from_user.username

    # Проверка, что администратор — это @shinbuu
    if username != "shinbuu":
        await update.message.reply_text("Only admins can approve characters.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Usage: /approve_character <character_id>")
        return

    char_id = int(context.args[0])

    cursor.execute("SELECT * FROM CharacterCreationRequests WHERE id = ?", (char_id,))
    result = cursor.fetchone()

    if result is None:
        await update.message.reply_text(f"No character found with ID {char_id}.")
        return

    user_id, character_name, flagged = result[1], result[2], result[3]

    # Now add the character to the Characters table
    cursor.execute(
        "INSERT INTO Characters (user_id, name, hp, attack, tier, mana, speed) "
        "SELECT user_id, character_name, 100, 30, 'B', 50, 20 FROM CharacterCreationRequests WHERE id = ?",
        (char_id,)
    )
    conn.commit()

    # Delete the character from the pending list
    cursor.execute("DELETE FROM CharacterCreationRequests WHERE id = ?", (char_id,))
    conn.commit()

    await update.message.reply_text(f"Character '{character_name}' has been approved and added to the game!")

# Command: /reject_character (Admin only)
async def reject_character(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    username = update.message.from_user.username

    # Проверка, что администратор — это @shinbuu
    if username != "shinbuu":
        await update.message.reply_text("Only admins can reject characters.")
        return

    if len(context.args) < 1:
        await update.message.reply_text("Usage: /reject_character <character_id>")
        return

    char_id = int(context.args[0])

    # Проверяем, существует ли запись в CharacterCreationRequests
    cursor.execute("SELECT * FROM CharacterCreationRequests WHERE id = ?", (char_id,))
    result = cursor.fetchone()

    if result is None:
        await update.message.reply_text(f"No character found with ID {char_id}.")
        return

    character_name = result[2]

    # Удаляем персонажа из таблицы Characters
    cursor.execute("DELETE FROM Characters WHERE name = ?", (character_name,))
    conn.commit()

    # Удаляем запись из таблицы CharacterCreationRequests
    cursor.execute("DELETE FROM CharacterCreationRequests WHERE id = ?", (char_id,))
    conn.commit()

    await update.message.reply_text(f"Character '{character_name}' has been rejected and removed from the database.")


# Command: /my_characters
async def my_characters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id
    cursor.execute("SELECT * FROM Characters WHERE user_id = ?", (user_id,))
    characters = cursor.fetchall()

    if not characters:
        await update.message.reply_text("You don't own any characters yet.")
        return

    message = "Your Characters:\n"
    for char in characters:
        message += f"Name: {char[2]}, HP: {char[3]}, Attack: {char[4]}, Tier: {char[5]}, Mana: {char[6]}, Speed: {char[7]}\n"

    await update.message.reply_text(message)

# Command: /open_case
async def open_case(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    # Simulate character creation
    tiers = ['C', 'B', 'A', 'S', 'GOD']
    tier = random.choices(tiers, weights=[50, 30, 15, 4, 1])[0]
    hp = random.randint(50, 200)
    attack = random.randint(10, 50)
    mana = random.randint(20, 100)
    speed = random.randint(5, 20)

    character_name = f"Random {tier} Character"

    cursor.execute(
        "INSERT INTO Characters (user_id, name, hp, attack, tier, mana, speed) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, character_name, hp, attack, tier, mana, speed)
    )
    conn.commit()

    await update.message.reply_text(
        f"Congratulations! You received a {tier} tier character:\n"
        f"Name: {character_name}, HP: {hp}, Attack: {attack}, Mana: {mana}, Speed: {speed}"
    )

# Command: /pvp
# Добавим таблицу для отслеживания игроков, желающих участвовать в PvP
cursor.execute(''' 
CREATE TABLE IF NOT EXISTS PvPQueue ( 
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    user_id INTEGER, 
    character_id INTEGER 
) 
''')
conn.commit()

# Модифицированная команда /pvp
async def pvp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.message.from_user.id

    # Проверяем, есть ли у игрока персонажи
    cursor.execute("SELECT * FROM Characters WHERE user_id = ?", (user_id,))
    user_characters = cursor.fetchall()

    if not user_characters:
        await update.message.reply_text("You need at least one character to fight!")
        return

    user_character = random.choice(user_characters)

    # Добавляем игрока в очередь на PvP
    cursor.execute("INSERT INTO PvPQueue (user_id, character_id) VALUES (?, ?)", (user_id, user_character[0]))
    conn.commit()

    # Ищем другого игрока, готового к бою
    cursor.execute("SELECT * FROM PvPQueue WHERE user_id != ? LIMIT 1", (user_id,))
    opponent = cursor.fetchone()

    if opponent:
        # Убираем игроков из очереди PvP
        cursor.execute("DELETE FROM PvPQueue WHERE id IN (?, ?)", (user_character[0], opponent[0]))
        conn.commit()

        # Получаем данные оппонента
        cursor.execute("SELECT * FROM Characters WHERE id = ?", (opponent[2],))
        opponent_character = cursor.fetchone()

        # Бой
        enemy_tier = opponent_character[5]
        enemy_hp = opponent_character[3]
        enemy_attack = opponent_character[4]
        enemy_speed = opponent_character[7]

        # Характеристики игрока
        user_hp = user_character[3]
        user_attack = user_character[4]
        user_speed = user_character[7]

        user_hp_remaining = user_hp
        enemy_hp_remaining = enemy_hp

        while user_hp_remaining > 0 and enemy_hp_remaining > 0:
            if user_speed >= enemy_speed:
                enemy_hp_remaining -= user_attack
                if enemy_hp_remaining <= 0:
                    break
                user_hp_remaining -= enemy_attack
            else:
                user_hp_remaining -= enemy_attack
                if user_hp_remaining <= 0:
                    break
                enemy_hp_remaining -= user_attack

        # Выводим результат
        if user_hp_remaining > 0:
            await update.message.reply_text(f"You won! Your character defeated {opponent_character[2]}.")
        else:
            await update.message.reply_text(f"You lost! {opponent_character[2]} defeated your character.")
    else:
        await update.message.reply_text("Waiting for an opponent... You will be matched soon!")

# Command: /tips
async def tips(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tips_list = [
        "Open gacha cases to get new characters.",
        "Use /pvp to test your characters' strength in battle.",
        "Submit your own characters for admin approval using /create_character."
    ]
    await update.message.reply_text("Here are some tips for the game:\n" + '\n'.join(tips_list))

# Main function to set up the bot
async def main() -> None:
    application = Application.builder().token(TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("create_character", create_character))
    application.add_handler(CommandHandler("review_characters", review_characters))
    application.add_handler(CommandHandler("approve_character", approve_character))
    application.add_handler(CommandHandler("reject_character", reject_character))
    application.add_handler(CommandHandler("my_characters", my_characters))
    application.add_handler(CommandHandler("open_case", open_case))
    application.add_handler(CommandHandler("pvp", pvp))
    application.add_handler(CommandHandler("tips", tips))

    # Start the bot
    logger.info("Starting the bot...")
    await application.run_polling(stop_signals=None)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
