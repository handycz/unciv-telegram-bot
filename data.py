from logging import getLogger
from typing import Any, Callable

from telegram.constants import ParseMode
from telegram.ext import JobQueue, Job, ContextTypes

from reader import read_gamefile

_logger = getLogger(__name__)


def has_games(user_data: dict[str, Any] | None) -> bool:
    return user_data and "games" in user_data


def get_game(user_data: dict[str, Any] | None, fltr: Callable[[dict[str, Any]], bool]):
    if not has_games(user_data):
        return None

    for game in user_data["games"]:
        if fltr(game):
            return game

    return None


async def create_notify_job(job_queue: JobQueue, registration_data: dict[str, Any]) -> Job:
    period = registration_data["period"]
    gameid = registration_data["gameid"]
    chatid = registration_data["chatid"]
    name = registration_data["name"]

    return job_queue.run_repeating(
        _notify,
        interval=period, first=period,
        data=name, chat_id=chatid,
        name=f"notify-{chatid}-{name}"
    )


async def _notify(context: ContextTypes.DEFAULT_TYPE):
    name = context.job.data
    user_data = context.application.user_data.get(context.job.chat_id, None)

    data = get_game(user_data, lambda g: g["name"] == name)

    if not data:
        _logger.warning("Removing orphan job user_id=%s, name=%s", context.job.user_id, name)
        context.job.enabled = False
        context.job.schedule_removal()

    player, turns = await read_gamefile(data["server"], data["gameid"], ["currentPlayer"], ["turns"])
    last_notify = data["last_notify"]

    if player != data["nation"]:
        _logger.debug("Not players turn, skipping. checked=%s, turn=%s", player, data["nation"])
        return

    if turns != last_notify:
        gameid = data["gameid"]
        data["last_notify"] = turns
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=f"It's your turn, {player}! Game: <b>{name}</b>, turn: {turns}. <a href='{get_game_link(gameid)}'>OPEN</a>",
            parse_mode=ParseMode.HTML
        )
    else:
        _logger.debug("Already notified, skipping")


def get_game_link(gameid: str) -> str:
    return f"https://unciv.app/multiplayer?id={gameid}"
