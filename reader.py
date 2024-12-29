from __future__ import annotations

import asyncio
import base64
import contextlib
import gzip
import json
import re
from typing import Any, Iterator

import aiohttp


@contextlib.asynccontextmanager
async def gamefile(server: str, game_id: str) -> Iterator[_Gamefile]:
    url = f"{server}/files/{game_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            payload = await response.read()
            decoded = base64.b64decode(payload)
            try:
                decompressed = gzip.decompress(decoded)
                text = decompressed.decode("utf8")
            except Exception:
                text = payload.decode("utf8")

    json_data = json.loads(text)
    yield _Gamefile(json_data)


class _Gamefile:
    _data: Any

    def __init__(self, data: Any):
        self._data = data
        
    def get_value(self, *path: list[str], required: bool = True) -> Any:
        local_data = self._data
        for key in path:
            try:
                local_data = local_data[key]
            except KeyError as err:
                if required:
                    raise err
                return None
        return local_data
