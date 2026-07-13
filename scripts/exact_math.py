#!/usr/bin/env python3
"""Small exact-arithmetic primitives used by certificate tools."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any


def ceil_div(a: int, b: int) -> int:
    if b <= 0:
        raise ValueError("denominator must be positive")
    return -(-a // b)


def strict_floor(value: Fraction) -> int:
    """Return the greatest integer strictly smaller than value."""
    return ceil_div(value.numerator, value.denominator) - 1


def ln_interval(x: int, terms: int = 192) -> tuple[Fraction, Fraction]:
    """Enclose ln(x) with the positive atanh series and a geometric tail."""
    if x <= 1 or terms < 1:
        raise ValueError("ln_interval requires x > 1 and terms > 0")
    z = Fraction(x - 1, x + 1)
    z2 = z * z
    power = z
    total = Fraction(0)
    for index in range(terms):
        total += power / (2 * index + 1)
        power *= z2
    lower = 2 * total
    tail = 2 * power / ((2 * terms + 1) * (1 - z2))
    return lower, lower + tail


def dyadic_lower(value: Fraction, bits: int) -> Fraction:
    scale = 1 << bits
    return Fraction((value.numerator * scale) // value.denominator, scale)


def dyadic_upper(value: Fraction, bits: int) -> Fraction:
    scale = 1 << bits
    return Fraction(ceil_div(value.numerator * scale, value.denominator), scale)


def logarithm_intervals(
    terms: int = 192, bits: int = 256
) -> dict[str, tuple[Fraction, Fraction]]:
    ln2_exact = ln_interval(2, terms)
    ln3_exact = ln_interval(3, terms)
    ln2 = (dyadic_lower(ln2_exact[0], bits), dyadic_upper(ln2_exact[1], bits))
    ln3 = (dyadic_lower(ln3_exact[0], bits), dyadic_upper(ln3_exact[1], bits))
    delta_exact = (ln3[0] / ln2[1], ln3[1] / ln2[0])
    delta = (
        dyadic_lower(delta_exact[0], bits),
        dyadic_upper(delta_exact[1], bits),
    )
    return {"ln2": ln2, "ln3": ln3, "delta": delta}


def fraction_json(value: Fraction) -> dict[str, str]:
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def parse_fraction(value: Any) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise ValueError("fraction must have numerator and denominator")
    numerator = value["numerator"]
    denominator = value["denominator"]
    if not isinstance(numerator, str) or not isinstance(denominator, str):
        raise ValueError("fraction components must be canonical decimal strings")
    if str(int(numerator)) != numerator or str(int(denominator)) != denominator:
        raise ValueError("noncanonical fraction component")
    result = Fraction(int(numerator), int(denominator))
    if result.denominator != int(denominator):
        raise ValueError("fraction is not reduced")
    return result


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def log2_upper_witness(value: int, denominator: int = 1000) -> Fraction:
    """Return the least p/q in the selected grid with 2^(p/q) > value."""
    if value <= 0 or denominator <= 0:
        raise ValueError("value and denominator must be positive")
    lower = (value.bit_length() - 1) * denominator
    upper = value.bit_length() * denominator
    target = pow(value, denominator)
    while lower < upper:
        middle = (lower + upper) // 2
        if (1 << middle) > target:
            upper = middle
        else:
            lower = middle + 1
    return Fraction(lower, denominator)


def geometric_sum(value: Fraction, terms: int) -> Fraction:
    if terms < 1:
        raise ValueError("terms must be positive")
    total = Fraction(1)
    power = Fraction(1)
    for _ in range(1, terms):
        power *= value
        total += power
    return total
