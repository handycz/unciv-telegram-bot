from datetime import timedelta, datetime
from logging import getLogger
from typing import Any, Callable

from telegram.constants import ParseMode
from telegram.ext import JobQueue, Job, ContextTypes, CallbackContext

from reader import read_gamefile

_logger = getLogger(__name__)


def has_games(user_data: dict[str, Any] | None) -> bool:
    return user_data and "games" in user_data and user_data["games"]


def get_game(user_data: dict[str, Any] | None, fltr: Callable[[dict[str, Any]], bool]):
    if not has_games(user_data):
        return None

    for game in user_data["games"]:
        if fltr(game):
            return game

    return None


def list_games(user_data: dict[str, Any] | None):
    if not has_games(user_data):
        return []

    return user_data["games"]

async def create_notify_job(job_queue: JobQueue, registration_data: dict[str, Any]) -> Job:
    period = registration_data["period"]
    gameid = registration_data["gameid"]
    chatid = registration_data["chatid"]
    name = registration_data["name"]

    return job_queue.run_repeating(
        _run_notification_task,
        interval=period, first=period,
        data=name, chat_id=chatid,
        name=f"notify-{chatid}-{name}"
    )


async def _run_notification_task(context: ContextTypes.DEFAULT_TYPE):
    name = context.job.data
    user_data = context.application.user_data.get(context.job.chat_id, None)

    job_data = get_game(user_data, lambda g: g["name"] == name)

    if not job_data:
        _remove_job(context)
        return
    
    current_player_nation, current_player_turn = await read_gamefile(job_data["server"], job_data["gameid"], ["currentPlayer"], ["turns"])
    last_notification_turn = job_data.get("last_notification_turn", -1) or job_data.get("last_notify")  # todo: remove deprecated `last_notify` use

    if current_player_nation != job_data["nation"]:
        _logger.debug("Not players turn, skipping. checked=%s, turn=%s", current_player_nation, job_data["nation"])
        return
    
    if current_player_turn > last_notification_turn:
        _logger.debug("Turn number changed, resetting turn notification state")
        job_data["last_notification_turn"] = current_player_turn
        current_turn_notification_count = 0
        next_notification_time = datetime.fromtimestamp(0).isoformat()
    else:
        current_turn_notification_count = job_data.get("current_turn_notification_count", 0)        
        next_notification_time = job_data.get("next_notification_time", datetime.fromtimestamp(0).isoformat())
        
    now = datetime.now()
    
    if now > datetime.fromisoformat(next_notification_time):
        gameid = job_data["gameid"]
        next_reminder = timedelta(seconds=_get_notification_time_difference_seconds(current_turn_notification_count + 1))
        job_data["next_notification_time"] = (now + next_reminder).isoformat()
        job_data["current_turn_notification_count"] = current_turn_notification_count + 1
        notification_text = (
            f"It's your turn, {current_player_nation}! "
            f"Game: <b>{name}</b>, turn: {current_player_turn}. <a href='{get_game_link(gameid)}'>OPEN</a>. "
            f"Next reminder in {next_reminder}."
        )
        
        await context.bot.send_message(
            chat_id=context.job.chat_id,
            text=notification_text,
            parse_mode=ParseMode.HTML
        )
    else:
        _logger.debug("Already notified, skipping")

def _get_notification_time_difference_seconds(notification_number: int) -> int:
    """ Return notification time difference in seconds """

    difference_minutes = notification_number**3 * 15
    return difference_minutes * 60

def _remove_job(context: CallbackContext) -> None:
        _logger.warning("Removing orphan job user_id=%s, name=%s", context.job.user_id, context.job.data)
        context.job.enabled = False
        context.job.schedule_removal()

def get_game_link(gameid: str) -> str:
    return f"https://unciv.app/multiplayer?id={gameid}"
