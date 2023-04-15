from logging import getLogger

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from data import has_games, get_game, create_notify_job
from datatypes import RegistrationStates, UnregistrationStates
from reader import read_gamefile


__all__ = [
    "list_registrations", "unregister", "start", "register", "register_name", "register_server", "register_cancel",
    "register_nation_failed", "register_nation_id", "register_gameid", "register_name_failed", "register_server_failed",
    "register_nation_name", "register_gameid_failed", "register_period_failed", "register_period", "unregister_name",
    "unregister_cancel"
]


_logger = getLogger(__name__)


async def list_registrations(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not has_games(context.user_data):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="You have no games registered")
        return

    rows = list()
    for game in context.user_data["games"]:
        name = game["name"]
        nation = game["nation"]
        server = game["server"]
        gameid = game["gameid"]
        period = game["period"]

        row = [f"<b># {name}</b>",
               f"    Nation: {nation}",
               f"    Game ID: {gameid}",
               f"    Server: {server}",
               f"    Period: {period} seconds"]

        rows.append("\n".join(row))

    text = '\n'.join(rows)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def unregister(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Enter the name of the game to be removed. List your games by /list. Cancel the unregistration by /cancel."
    )

    return UnregistrationStates.NAME


async def unregister_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text

    game = get_game(context.user_data, lambda g: g["name"] == name)
    if not game:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Wrong game name. Try again."
        )
        return UnregistrationStates.NAME

    job, = context.job_queue.get_jobs_by_name(game["job_name"])
    job.enabled = False
    context.job_queue.scheduler.remove_job(job.job.id)
    context.user_data["games"].remove(game)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Game unregistered."
    )

    return ConversationHandler.END


async def unregister_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Cancelling the unregistration process. Yay!")
    return ConversationHandler.END


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands = [
        "/register\tSubscribe a new watcher",
        "/unregister\tRemove a watcher",
        "/list\tList all watchers"
    ]
    commands_str = '\n'.join(commands)
    await update.message.reply_text(
        text=f"The bot allows subscribe to a turn notification of an "
             f"Unciv multiplayer game. Supported commands: \n{commands_str}"
    )


async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Starting the registration process... You can always /cancel to abort the registration"
    )

    context.user_data['registration'] = dict()

    await _ask_name(update, context)
    return RegistrationStates.NAME


async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text

    if get_game(context.user_data, lambda g: g["name"] == name):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Name already in use, try a different one"
        )
        return RegistrationStates.NAME

    context.user_data['registration']['name'] = name
    await _ask_server(update, context)
    return RegistrationStates.SERVER


async def register_name_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Name can only contain alphanumeric characters, spaces, dashes and underscores. Try again."
    )
    await _ask_name(update, context)
    return RegistrationStates.NAME


async def register_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['registration']['server'] = update.message.text
    await _ask_gameid(update, context)
    return RegistrationStates.GAME_ID


async def register_server_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="URL invalid. Try again.")
    await _ask_server(update, context)
    return RegistrationStates.SERVER


async def register_gameid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['registration']['gameid'] = update.message.text
    await _ask_nation(update, context)
    return RegistrationStates.NATION


async def register_gameid_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Game ID has incorrect format. Try again.")
    await _ask_gameid(update, context)
    return RegistrationStates.GAME_ID


async def register_nation_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    players = await read_gamefile(
        context.user_data['registration']['server'],
        context.user_data['registration']['gameid'],
        ["gameParameters", "players"]
    )
    civ_name = None
    for player in players:
        if player.get("playerId", None) == update.message.text:
            civ_name = player["chosenCiv"]

    if not civ_name:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Player ID not found in the game. Try again.")
        return RegistrationStates.NATION

    context.user_data['registration']['nation'] = civ_name
    await _ask_period(update, context)
    return RegistrationStates.PERIOD


async def register_nation_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    players = await read_gamefile(
        context.user_data['registration']['server'],
        context.user_data['registration']['gameid'],
        ["gameParameters", "players"]
    )
    playerId = None
    for player in players:
        if player.get("chosenCiv", None).lower() == update.message.text.lower():
            playerId = player["playerId"]

    if not playerId:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Chosen civ is not a human player. Try again.")
        return RegistrationStates.NATION

    context.user_data['registration']['nation'] = update.message.text.capitalize()
    await _ask_period(update, context)
    return RegistrationStates.PERIOD


async def register_nation_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Supplied string is not a nation name nor it is a Client ID. Try again.")
    await _ask_nation(update, context)
    return RegistrationStates.NATION


async def register_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        period = float(update.message.text)
    except ValueError:
        period = None
    if not period or period < 10:
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text="Period must be a number greater or equal to 10")
        return RegistrationStates.PERIOD

    await _finish_registration(period, update, context)

    return ConversationHandler.END


async def register_period_failed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Supplied period is not a valid number. Try again.")
    await _ask_period(update, context)
    return RegistrationStates.PERIOD


async def register_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Cancelling the registration process. Your loss.")
    context.user_data['registration'] = dict()
    return ConversationHandler.END


async def _ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Enter arbitrary game name"
    )


async def _ask_server(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Enter server name"
    )


async def _ask_gameid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Enter Game ID"
    )


async def _ask_nation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Enter nation name or Client ID"
    )


async def _ask_period(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Enter refresh period (in seconds)"
    )


async def _finish_registration(period: float, update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    registration_data = context.user_data["registration"]
    del context.user_data["registration"]

    registration_data["chatid"] = chat_id
    registration_data["last_notify"] = -1
    registration_data["period"] = period

    job = await create_notify_job(context.job_queue, registration_data)

    if "games" not in context.user_data:
        context.user_data["games"] = list()

    registration_data["job_name"] = job.name
    context.user_data["games"].append(registration_data)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="That would be all, thanks... Remember you can always /unregister to cancel the registration"
    )
