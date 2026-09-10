from resto.domain.services.content_hash import compute_content_hash


def test_content_hash_is_deterministic() -> None:
    assert compute_content_hash("a", 1, {"b": 2}) == compute_content_hash("a", 1, {"b": 2})


def test_content_hash_differs_for_different_input() -> None:
    assert compute_content_hash("a") != compute_content_hash("b")
