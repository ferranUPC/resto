"""Code-made noise for request variants: reproducible, free, and it never touches a token with a
digit (ids such as `B0C0`, times, numbers), since a typo there would change the gold."""

from __future__ import annotations

import random
import re
import unicodedata
import zlib

_WORD = re.compile(r"\w+", re.UNICODE)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return unicodedata.normalize(
        "NFC", "".join(c for c in decomposed if not unicodedata.combining(c))
    )


def add_typos(text: str, seed: str, rate: float = 0.15) -> str:
    rng = random.Random(zlib.crc32(seed.encode()))

    def mangle(match: re.Match[str]) -> str:
        word = match.group(0)
        if len(word) < 4 or any(c.isdigit() for c in word) or rng.random() >= rate:
            return word
        i = rng.randrange(1, len(word) - 1)
        op = rng.choice(("swap", "drop", "double"))
        if op == "swap":
            return word[:i] + word[i + 1] + word[i] + word[i + 2 :]
        if op == "drop":
            return word[:i] + word[i + 1 :]
        return word[:i] + word[i] + word[i:]

    return _WORD.sub(mangle, text)
