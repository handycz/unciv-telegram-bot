import logging
from pathlib import Path

from telegram.ext import ApplicationBuilder, CommandHandler, ConversationHandler, MessageHandler, filters, \
    PicklePersistence, Application, CallbackQueryHandler
from telegram.ext.filters import UpdateType

from data import create_notify_job, has_games
from datatypes import Config, RegistrationStates, UnregistrationStates
from handlers import *

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

_logger = logging.getLogger(__name__)

config = Config()

id_filter = filters.Regex(r"^[a-zA-Z0-9]{8}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{4}-[a-zA-Z0-9]{12}$")
name_filter = filters.Regex(r"^[a-zA-Z_\- ]+$")


async def initialize_jobs(app: Application):
    _logger.info("Initializing jobs from persistance store")
    for chat_id, user_data in app.user_data.items():
        if has_games(user_data):
            for game in user_data["games"]:
                _logger.debug("initializing %s", game)
                await create_notify_job(app.job_queue, game)
        else:
            _logger.debug("chat_id %s has no games, skipping", chat_id)


if __name__ == '__main__':
    persistence = PicklePersistence(str(Path("/data/storage.pickle")))

    application = ApplicationBuilder().token(
        config.CHAT_TOKEN
    ).persistence(
        persistence
    ).post_init(
        initialize_jobs
    ).build()

    start_handler = CommandHandler(['start', 'help'], start, filters=~UpdateType.EDITED_MESSAGE)
    application.add_handler(start_handler)

    list_handler = CommandHandler('list', list_registrations, filters=~UpdateType.EDITED_MESSAGE)
    application.add_handler(list_handler)

    register_handler = ConversationHandler(
        entry_points=[CommandHandler("register", register)],
        states={
            RegistrationStates.NAME: [
                CommandHandler("cancel", register_cancel),
                MessageHandler(filters.TEXT & name_filter, register_name),
                MessageHandler(filters.ALL, register_name_failed)
            ],
            RegistrationStates.SERVER: [
                CommandHandler("cancel", register_cancel),
                CallbackQueryHandler(register_server),
                MessageHandler(filters.TEXT & filters.Regex("^((http|https)://)[-a-zA-Z0-9@:%._\\+~#?&//=]{2,256}\\.[a-z]{2,6}\\b([-a-zA-Z0-9@:%._\\+~#?&//=]*)$"), register_server),
                MessageHandler(filters.ALL, register_server_failed)
            ],
            RegistrationStates.GAME_ID: [
                CommandHandler("cancel", register_cancel),
                MessageHandler(filters.TEXT & id_filter, register_gameid),
                MessageHandler(filters.ALL, register_gameid_failed)
            ],
            RegistrationStates.NATION: [
                CommandHandler("cancel", register_cancel),
                CallbackQueryHandler(register_nation_name),
                MessageHandler(filters.TEXT & name_filter, register_nation_name),
                MessageHandler(filters.ALL, register_nation_failed)
            ],
            RegistrationStates.PERIOD: [
                CommandHandler("cancel", register_cancel),
                MessageHandler(filters.TEXT, register_period),
                MessageHandler(filters.ALL, register_period_failed)
            ],
        },
        fallbacks=[CommandHandler("cancel", register_cancel)],
    )

    application.add_handler(register_handler)

    unregister_handler = ConversationHandler(
        entry_points=[CommandHandler("unregister", unregister)],
        states={
            UnregistrationStates.NAME: [
                CallbackQueryHandler(unregister_id),
                MessageHandler(filters.TEXT & name_filter, unregister_id),
            ],
        },
        fallbacks=[CommandHandler("cancel", unregister_cancel)],
    )

    application.add_handler(unregister_handler)

    application.run_polling()
