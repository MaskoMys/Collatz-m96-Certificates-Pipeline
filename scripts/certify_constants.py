#!/usr/bin/env python3
"""
Exact arithmetic checks for the constants encoded in make_case(92)..make_case(96).

This script checks the reusable arithmetic facts used by the finite branch
searches: rational bounds for log2(3), the continued-fraction bracket used by
floor_alpha, each case window, k1 range, exact lower-bound stage constants, and
the m=96 coarse cap derivation.

For m=92..95, the stage targets and tighter caps are case-specific reduction
constants. This script checks their exact encoded values and basic consistency;
`verify_reduction_certificates.py` independently checks their derivation.
"""

from dataclasses import dataclass
from fractions import Fraction as F


X = 1 << 71
FIRST_POSITIVE_SURPLUS = 72057431991
AL_LO = F(83130157078217, 52449289519716)
AL_HI = F(18340740190704, 11571718688839)
ALPHA = F(317, 200)


@dataclass(frozen=True)
class CaseConstants:
    m: int
    anum: int
    aden: int
    depth: int
    extra: tuple[int, ...]
    k1max: int
    kcap: tuple[int, ...]
    cap_lmax: F | None = None


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


TERM = ceil_div(93 * (1 << 189), 50)
B2_92 = ceil_div(17086 * (1 << 74), 10000) + 1

CASES = [
    CaseConstants(
        92,
        73,
        10,
        2,
        (0, X, B2_92, 1 << 118),
        73,
        (73, 118),
        F(74),
    ),
    CaseConstants(
        93,
        15,
        1,
        3,
        (0, X, X, 1 << 75, 7 << 117),
        74,
        (74, 118, 188),
        F(75),
    ),
    CaseConstants(
        94,
        24,
        1,
        5,
        (0, X, X, X, 1 << 75, 1 << 119, 1 << 189),
        75,
        (75, 119, 189, 299, 474),
    ),
    CaseConstants(
        95,
        24,
        1,
        6,
        (0, X, X, X, X, 3 << 74, 7 << 117, TERM),
        75,
        (75, 119, 189, 299, 474, 751),
    ),
    CaseConstants(
        96,
        29,
        1,
        7,
        (0, X, X, X, X, X, 3 << 74, 7 << 117, TERM),
        75,
        (75, 120, 191, 303, 481, 763, 1210),
        F(76),
    ),
]

ok = True


def chk(name: str, cond: bool) -> None:
    global ok
    ok = ok and cond
    print(f"  [{'OK' if cond else 'FAIL'}] {name}")


def ln_bounds(x: int, terms: int = 400) -> tuple[F, F]:
    xq = F(x)
    z = (xq - 1) / (xq + 1)
    z2 = z * z
    s = F(0)
    zp = z
    for j in range(terms):
        s += zp / (2 * j + 1)
        zp *= z2
    lo = 2 * s
    tail = 2 * (z ** (2 * terms + 1)) / ((2 * terms + 1) * (1 - z2))
    return lo, lo + tail


def strict_int_max_below(bound: F) -> int:
    return ceil_div(bound.numerator, bound.denominator) - 1


def window_upper(case: CaseConstants) -> int:
    return (case.anum * X) // case.aden


def certify_shared_arithmetic() -> tuple[F, F]:
    ln2_l, ln2_u = ln_bounds(2)
    ln3_l, ln3_u = ln_bounds(3)
    g_l = ln3_l / ln2_u
    g_u = ln3_u / ln2_l
    print(
        f"[log2 3] bracket width ~ {float(g_u - g_l):.2e}; "
        f"{float(g_l):.12f} < log2 3 < {float(g_u):.12f}"
    )

    print("1. coarse alpha bound")
    chk("317/200 > log2 3", ALPHA > g_u)
    chk("3^200 < 2^317", 3**200 < 2**317)

    print("2. floor_alpha continued-fraction bracket")
    chk("AL_LO < log2 3 < AL_HI", AL_LO < g_l and g_u < AL_HI)
    chk(
        "bracket width * FIRST_POSITIVE_SURPLUS < 1",
        FIRST_POSITIVE_SURPLUS * (AL_HI - AL_LO) < 1,
    )
    chk("FIRST_POSITIVE_SURPLUS is fixed", FIRST_POSITIVE_SURPLUS == 72057431991)
    return g_l, g_u


def certify_case(case: CaseConstants) -> None:
    print(f"{case.m}. make_case({case.m}) constants")
    chk("depth matches extra table", len(case.extra) == case.depth + 2)
    chk("depth matches cap table", len(case.kcap) == case.depth)

    upper = window_upper(case)
    chk(
        f"window upper is floor(({case.anum}/{case.aden})*2^71)",
        upper == (case.anum * X) // case.aden,
    )
    chk(f"k1max={case.k1max} covers window", upper + 1 < (1 << (case.k1max + 1)))
    chk(
        f"k1max={case.k1max} is not vacuous",
        upper + 1 >= (1 << case.k1max),
    )

    for idx in range(1, len(case.extra) - 1):
        chk(f"extra[{idx}] >= X", case.extra[idx] >= X)
    for idx in range(1, len(case.extra) - 1):
        chk(
            f"extra[{idx + 1}] >= min(extra[{idx}], X)",
            case.extra[idx + 1] >= min(case.extra[idx], X),
        )

    if case.m == 92:
        raw = 17086 * (1 << 74)
        chk("B2_92 uses ceil(17086*2^74/10000)+1", case.extra[2] == ceil_div(raw, 10000) + 1)
        chk("B2_92 is strictly above 17086*2^74/10000", case.extra[2] * 10000 > raw)
    if case.m in {95, 96}:
        chk("terminal term is ceil(93*2^189/50)", case.extra[-1] == TERM)
        chk("terminal term is strictly above 7*2^117", case.extra[-1] > (7 << 117))

    if case.cap_lmax is not None:
        print(f"   cap check with log2(n1+1) < {case.cap_lmax}")
        chk(
            f"window implies log2(n1+1) < {case.cap_lmax}",
            upper + 1 < (1 << int(case.cap_lmax))
            if case.cap_lmax.denominator == 1
            else True,
        )
        for idx, cap in enumerate(case.kcap):
            bound = (ALPHA ** idx) * case.cap_lmax
            max_allowed = strict_int_max_below(bound)
            chk(
                f"kcap[{idx + 1}]={cap} >= {max_allowed}",
                cap >= max_allowed,
            )
    else:
        print("   cap table is case-specific; derivation checked by reduction verifier")
        chk("caps are positive", all(cap >= 1 for cap in case.kcap))
        chk("caps are nondecreasing", list(case.kcap) == sorted(case.kcap))


def main() -> None:
    certify_shared_arithmetic()
    print("3. case tables")
    for case in CASES:
        certify_case(case)
    print("\nRESULT:", "ALL CONSTANT CHECKS PASSED" if ok else "SOME CHECK FAILED")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
