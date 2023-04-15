import asyncio
import base64
import gzip
import re
from typing import Any

import aiohttp

import json as jsonp


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

    json = load_crippled_json(text)
    values = _get_values(json, keys)
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


class ParserError(Exception):
    def __init__(self, msg: str):
        super().__init__(msg)


def load_crippled_json(data: str) -> dict[Any, Any]:
    data = data.strip()

    index = 0

    stack = list()
    result = None

    while index < len(data):
        def parse_string_literal():
            nonlocal index
            nonlocal char

            escaped = False
            literal = []

            while True:
                if index >= len(data):
                    raise ParserError("EOF")

                char = data[index]
                if char == "\\":
                    escaped = True
                elif char == '"':
                    if escaped:
                        literal += char
                    else:
                        index += 1
                    return "".join(literal)
                else:
                    literal += char

                index += 1

        def parse_literal():
            nonlocal index
            nonlocal char

            literal = list()

            while True:
                if index >= len(data):
                    raise ParserError("EOF")

                char = data[index]

                if char == "," or char == "]" or char == "}":
                    str_literal = "".join(literal)
                    if re.match(r'^-?[0-9]+$', str_literal):
                        return int(str_literal)

                    return str_literal

                literal += char
                index += 1

        def parse_identifier():
            nonlocal index
            nonlocal char
            nonlocal identifier

            identifier = list()

            while True:
                if index >= len(data):
                    raise ParserError("EOF")

                char = data[index]

                if char == ":":
                    index += 1
                    break
                else:
                    identifier += char
                    index += 1

            return "".join(identifier)

        current_index = len(stack) - 1
        current = stack[current_index] if 0 <= current_index < len(stack) else None
        context = (current.get('ctx', None) if current else None) or "definition"

        if context in ["object-property", "array-item", "definition"]:
            char = data[index]

            def assign(item):
                nonlocal current
                nonlocal result

                if current:
                    if current['ctx'] == "object-property":
                        current['object'][current['identifier']] = item
                    elif current['ctx'] == "array-item":
                        current['array'].append(item)
                    else:
                        raise ParserError(f"Assign to what? {current['ctx']}?")
                else:
                    result = item

            if char == "{":
                index += 1
                obj = {}
                assign(obj)
                if stack: stack.pop()
                stack.append({'ctx': 'object', 'object': obj})

            elif char == "[":
                index += 1
                arr = []
                assign(arr)
                if stack: stack.pop()
                stack.append({'ctx': 'array', 'array': arr})

            elif char == '"':
                index += 1
                assign(parse_string_literal())
                stack.pop()

            elif char == "}" or char == "]":
                index += 1
                # POP PROPERTY
                if stack: stack.pop()
                # POP OBJECT/ARRAY
                if stack: stack.pop()

            elif char == ",":
                index += 1

            else:
                assign(parse_literal())
                if stack: stack.pop()
        elif context == "object":
            char = data[index]

            if char == ",":
                index += 1

            elif char == "}":
                index += 1
                if stack: stack.pop()

            else:
                identifier = parse_identifier()

                stack.append({
                    'ctx': 'object-property',
                    'object': current['object'],
                    'identifier': identifier
                })

        elif context == "array":
            char = data[index]

            if char == ",":
                index += 1

            elif char == "]":
                index += 1
                if stack: stack.pop()

            else:
                stack.append({'ctx': 'array-item', 'array': current['array']})

    return result


if __name__ == "__main__":
    x = asyncio.run(read_gamefile("https://uncivserver.xyz", "5e13171c-8b85-47b1-8be3-7a7c83a6ab24", ["turns"], ["currentPlayer"]))
    print(x)
    print(type(x))
