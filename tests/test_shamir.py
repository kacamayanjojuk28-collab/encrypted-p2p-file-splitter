import pytest

from src.shamir_module import reconstruct_key, split_key


def test_shamir_round_trip_requires_three_shares() -> None:
    key = bytes(range(32))
    shares = split_key(key)

    assert reconstruct_key(shares) == key

    with pytest.raises(ValueError, match="Exactly 3 key shares"):
        reconstruct_key(shares[:2])
