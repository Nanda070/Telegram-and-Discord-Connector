import discord
from discord.ext import commands
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
import asyncio
from aiogram.filters import Command
from aiogram import Router

# ====== CONFIG ======
DISCORD_TOKEN = "MTMzNTMyMTUxNDY1MTY4NTA0Ng.GWkU74.ABzsRkX1W7PPUs9muTumy3Y3hT7Pb4LgNHmF3I"
TELEGRAM_TOKEN = "7919818538:AAEIjEwU2vQOplhoV_S2FXqfEj5pWNtJOi0"
DISCORD_GUILD_ID = 1139578692159414382  # ID вашего сервера Discord
DISCORD_CHANNEL_ID = 1139591871820214293  # ID канала в Discord
TELEGRAM_CHAT_ID = -1002315340645  # ID группы в Telegram
ADMIN_ROLE_ID = 1325381399708176424  # ID роли для управления
LOG_CHANNEL_ID = 1335322176827691058  # Канал для логов

message_map = {}  # {tg_message_id: discord_message_id, discord_message_id: tg_message_id}

sync_enabled = True  # Sync Flag

# ====== DISCORD BOT ======
intents = discord.Intents.all()
discord_bot = commands.Bot(command_prefix="/", intents=intents)

def has_admin_role(ctx):
    """Проверяет, есть ли у пользователя нужная роль."""
    return any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)


@discord_bot.event
async def on_ready():
    print(f"{discord_bot.user} запущен!")


@discord_bot.command()
@commands.check(has_admin_role)
async def sync_on(ctx):
    global sync_enabled
    sync_enabled = True
    await ctx.send("✅ Синхронизация включена!")


@discord_bot.command()
@commands.check(has_admin_role)
async def sync_off(ctx):
    global sync_enabled
    sync_enabled = False
    await ctx.send("❌ Синхронизация выключена!")


@discord_bot.command()
async def status(ctx):
    status_msg = "🟢 Включена" if sync_enabled else "🔴 Выключена"
    await ctx.send(f"Синхронизация: {status_msg}")


@discord_bot.event
async def on_message(message):
    if message.author.bot or not sync_enabled or message.channel.id != DISCORD_CHANNEL_ID:
        return

    text = f"[Discord] {message.author.name}: {message.content}"
    tg_msg = await tg_bot.send_message(TELEGRAM_CHAT_ID, text)

    message_map[message.id] = tg_msg.message_id  # Сохраняем соответствие сообщений

    log_channel = discord_bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(f"📜 LOG: {text}")

    await discord_bot.process_commands(message)

@discord_bot.event
async def on_message_edit(before, after):
    """Обновляет сообщение в Telegram при изменении в Discord."""
    if before.id not in message_map:
        print("⚠️ Сообщение не найдено в message_map, пропускаем.")
        return

    tg_message_id = message_map[before.id]

    try:
        new_text = f"[Discord] {before.author.name}: {after.content}"
        await tg_bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=tg_message_id, text=new_text)
        print(f"✏️ Сообщение обновлено в Telegram: {new_text}")
    except Exception as e:
        print(f"❌ Ошибка при обновлении сообщения в Telegram: {e}")

dp = Dispatcher()  # Создаём диспетчер
router = Router()  # Создаём роутер
dp.include_router(router)  # Добавляем роутер в диспетчер


@router.edited_message()
async def tg_message_edit(message: Message):
    """Обновляет сообщение в Discord при изменении в Telegram."""
    if message.message_id not in message_map:
        print("⚠️ Сообщение не найдено в message_map, пропускаем.")
        return

    discord_message_id = message_map[message.message_id]
    discord_channel = discord_bot.get_channel(DISCORD_CHANNEL_ID)

    if discord_channel is None:
        discord_channel = await discord_bot.fetch_channel(DISCORD_CHANNEL_ID)

    try:
        discord_msg = await discord_channel.fetch_message(discord_message_id)
        new_text = f"[Telegram] {message.from_user.first_name}: {message.text or ''}"
        await discord_msg.edit(content=new_text)
        print(f"✏️ Сообщение обновлено в Discord: {new_text}")
    except Exception as e:
        print(f"❌ Ошибка при обновлении сообщения в Discord: {e}")

# ====== TELEGRAM BOT ======
tg_bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

router = Router()
dp.include_router(router)

@router.message()
async def tg_to_discord(message: Message):
    if not sync_enabled:
        print("⏸ Синхронизация выключена.")
        return

    author = message.from_user.first_name
    text = f"[Telegram] {author}: {message.text or ''}"

    discord_channel = discord_bot.get_channel(DISCORD_CHANNEL_ID)
    if not discord_channel:
        print("❌ Ошибка: Discord канал не найден!")
        return

    try:
        discord_msg = await discord_channel.send(text)
        message_map[message.message_id] = discord_msg.id  # Сохраняем связь сообщений
        print("✅ Сообщение переслано в Discord.")
    except Exception as e:
        print(f"❌ Ошибка при отправке в Discord: {e}")

        # Логирование
        if log_channel:
            await log_channel.send(f"📜 LOG: {text}")


@router.message()
async def tg_message_delete(message: Message):
    """Удаляет сообщение в Discord при удалении в Telegram."""
    if message.message_id not in message_map:
        print("⚠️ Сообщение не найдено в message_map, пропускаем.")
        return

    discord_message_id = message_map.pop(message.message_id, None)
    discord_channel = discord_bot.get_channel(DISCORD_CHANNEL_ID)

    if discord_channel is None:
        discord_channel = await discord_bot.fetch_channel(DISCORD_CHANNEL_ID)

    try:
        discord_msg = await discord_channel.fetch_message(discord_message_id)
        await discord_msg.delete()
        print(f"🗑 Сообщение удалено в Discord.")
    except Exception as e:
        print(f"❌ Ошибка при удалении сообщения в Discord: {e}")

@discord_bot.event
async def on_message_delete(message):
    """Удаляет сообщение в Telegram при удалении в Discord."""
    if message.id not in message_map:
        print("⚠️ Сообщение не найдено в message_map, пропускаем.")
        return

    tg_message_id = message_map.pop(message.id, None)

    try:
        await tg_bot.delete_message(chat_id=TELEGRAM_CHAT_ID, message_id=tg_message_id)
        print(f"🗑 Сообщение удалено в Telegram.")
    except Exception as e:
        print(f"❌ Ошибка при удалении сообщения в Telegram: {e}")

async def start_telegram_bot():
    """Запускает Telegram-бота."""
    await dp.start_polling(tg_bot)


# ====== ЗАПУСК ОБОИХ БОТОВ ======
async def main():
    """Запускает Telegram и Discord ботов вместе."""
    loop = asyncio.get_event_loop()
    loop.create_task(start_telegram_bot())  # Запускаем Telegram
    await discord_bot.start(DISCORD_TOKEN)  # Запускаем Discord


if __name__ == "__main__":
    async def main():
        loop = asyncio.get_event_loop()
        loop.create_task(start_telegram_bot())  # Telegram бот
        await discord_bot.start(DISCORD_TOKEN)  # Discord бот


    asyncio.run(main())  # Запуск
