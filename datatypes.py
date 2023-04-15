import enum

import pydantic


class Config(pydantic.BaseSettings):
    CHAT_TOKEN: str


class RegistrationStates(enum.IntEnum):
    START = enum.auto()
    NAME = enum.auto()
    SERVER = enum.auto()
    GAME_ID = enum.auto()
    NATION = enum.auto()
    PERIOD = enum.auto()


class UnregistrationStates(enum.IntEnum):
    START = enum.auto()
    NAME = enum.auto()
