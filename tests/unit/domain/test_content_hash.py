"""Working-directory names derived from a hash (`work_key`, `short_hash`)."""

from __future__ import annotations

import hashlib

from resto.domain.services.content_hash import short_hash, work_key


def test_a_work_key_is_the_first_16_hex_characters_of_the_sha256() -> None:
    assert work_key("abc") == hashlib.sha256(b"abc").hexdigest()[:16]
    assert work_key(b"abc") == work_key("abc")


def test_a_short_hash_keeps_the_start_of_a_digest() -> None:
    assert short_hash("0123456789abcdef0123") == "0123456789abcdef"
