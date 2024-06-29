import asyncio
import base64
import gzip
import re
from typing import Any

import aiohttp

import json


async def read_gamefile(server: str, game_id: str, *keys: list[str]):
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

    values = _get_values(json_data, keys)
    if len(values) == 1:
        return values[0]

    return values


def _get_values(data, keysets: tuple[list[str]]) -> list[Any]:
    out = list()
    for keyset in keysets:
        local_data = data
        for key in keyset:
            local_data = local_data[key]
        out.append(local_data)

    return out
