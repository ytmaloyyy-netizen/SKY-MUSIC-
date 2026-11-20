from __future__ import annotations

import asyncio
import logging
import shutil
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import config
from bot.database.database import db
from bot.utils.logger import setup_logger
from bot.middlewares.auth import AuthAndMaintenanceMiddleware
from bot.middlewares.limits import AntiDoubleClickMiddleware

from bot.handlers import (
    start,
    menu,
    profile,
    audio,
    spatial,
    vocals,
    editor,
    search,
    effects,
    developer,
)

logger = setup_logger(config.logs_dir)


def _cleanup_stale_temp(temp_root) -> None:
    if not temp_root.exists():
        return
    for child in temp_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except OSError:
                pass


async def _register_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="🎧 Главное меню SKY MUSIC"),
        BotCommand(command="myid", description="🆔 Узнать свой Telegram ID"),
        BotCommand(command="profile", description="👤 Мой профиль и лимиты"),
        BotCommand(command="dev", description="👑 Панель разработчика (только Dev)"),
        BotCommand(command="users", description="👥 Пользователи (только Dev)"),
        BotCommand(command="stats", description="📊 Статистика (только Dev)"),
        BotCommand(command="broadcast", description="📢 Рассылка (только Dev)"),
        BotCommand(command="maintenance", description="🛠️ Тех. работы (только Dev)"),
    ]
    await bot.set_my_commands(commands)


async def run_bot() -> None:
    if not config.bot_token:
        raise RuntimeError(
            "BOT_TOKEN не задан! Укажите токен бота в файле .env (см. .env.example)."
        )

    if not config.is_developer_configured:
        logger.warning(
            "DEVELOPER_ID не задан в .env (текущее значение: %s). "
            "Укажите ваш Telegram ID в DEVELOPER_ID перед запуском в продакшене.",
            config.developer_id,
        )

    _cleanup_stale_temp(config.temp_dir)
    await db.connect()
    logger.info("База данных подключена: %s", config.database_path)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем middleware на уровне сообщений и коллбэков
    auth_mw = AuthAndMaintenanceMiddleware()
    anti_double_mw = AntiDoubleClickMiddleware()

    dp.message.middleware(auth_mw)
    dp.callback_query.middleware(auth_mw)
    dp.callback_query.middleware(anti_double_mw)

    # Подключаем все роутеры в логическом порядке приоритета
    dp.include_router(start.router)
    dp.include_router(developer.router)
    dp.include_router(profile.router)
    dp.include_router(audio.router)
    dp.include_router(spatial.router)
    dp.include_router(vocals.router)
    dp.include_router(editor.router)
    dp.include_router(search.router)
    dp.include_router(effects.router)
    dp.include_router(menu.router)

    try:
        await _register_commands(bot)
        logger.info("SKY MUSIC запущен (часовой пояс: %s)", config.timezone_name)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        logger.info("Остановка SKY MUSIC и закрытие соединений...")
        await db.close()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем.")


if __name__ == "__main__":
    main()
