from __future__ import annotations

import secrets


PRIME = 2**521 - 1
THRESHOLD = 3
SHARE_COUNT = 3
KEY_SIZE_BYTES = 32


def _eval_polynomial(secret: int, coefficients: list[int], x_value: int) -> int:
    result = secret
    power = x_value
    for coefficient in coefficients:
        result = (result + coefficient * power) % PRIME
        power = (power * x_value) % PRIME
    return result


def split_key(key: bytes) -> list[dict[str, str | int]]:
    if len(key) != KEY_SIZE_BYTES:
        raise ValueError("AES-256 key must be exactly 32 bytes")

    secret = int.from_bytes(key, "big")
    coefficients = [secrets.randbelow(PRIME - 1) + 1 for _ in range(THRESHOLD - 1)]
    shares: list[dict[str, str | int]] = []
    for x_value in range(1, SHARE_COUNT + 1):
        y_value = _eval_polynomial(secret, coefficients, x_value)
        shares.append(
            {
                "x": x_value,
                "y": hex(y_value),
                "threshold": THRESHOLD,
                "prime": hex(PRIME),
            }
        )
    return shares


def reconstruct_key(shares: list[dict[str, str | int]]) -> bytes:
    if len(shares) != THRESHOLD:
        raise ValueError("Exactly 3 key shares are required for 3-of-3 reconstruction")

    points: list[tuple[int, int]] = []
    seen_x: set[int] = set()
    for share in shares:
        if int(share.get("threshold", THRESHOLD)) != THRESHOLD:
            raise ValueError("Key share threshold metadata is invalid")
        share_prime = int(str(share.get("prime", hex(PRIME))), 16)
        if share_prime != PRIME:
            raise ValueError("Key share prime metadata is invalid")
        x_value = int(share["x"])
        if x_value in seen_x:
            raise ValueError(f"Duplicate key share x value: {x_value}")
        seen_x.add(x_value)
        points.append((x_value, int(str(share["y"]), 16)))

    secret = 0
    for i, (x_i, y_i) in enumerate(points):
        numerator = 1
        denominator = 1
        for j, (x_j, _) in enumerate(points):
            if i == j:
                continue
            numerator = (numerator * (-x_j)) % PRIME
            denominator = (denominator * (x_i - x_j)) % PRIME
        lagrange = numerator * pow(denominator, -1, PRIME)
        secret = (secret + y_i * lagrange) % PRIME

    if secret >= 2 ** (KEY_SIZE_BYTES * 8):
        raise ValueError("Reconstructed secret is outside AES-256 key range")
    return secret.to_bytes(KEY_SIZE_BYTES, "big")
