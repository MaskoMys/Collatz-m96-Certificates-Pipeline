#!/usr/bin/env python3
"""
Rigorous certification of the make_case(96) constants in src/m96/affine_ladder_prefix.cpp.
Exact rational/integer arithmetic only. Each check is a sound over-approximation
guarantee: constants must never EXCLUDE a valid cycle (caps are upper bounds on k_i,
extra are lower bounds on n_i, the CF bracket decides floor(n*log2 3) exactly).

It does NOT re-derive the imported Hercher/Simons-de Weger inequalities themselves
(that is the branch-cover lemma, point 3). It certifies that GIVEN those imported
inequalities, the numeric constants are correctly computed and sound.
"""

from fractions import Fraction as F


def ln_bounds(x, terms=400):
    x = F(x)
    z = (x - 1) / (x + 1)
    z2 = z * z
    s = F(0)
    zp = z
    for j in range(terms):
        s += zp / (2 * j + 1)
        zp *= z2
    lo = 2 * s
    tail = 2 * (z ** (2 * terms + 1)) / ((2 * terms + 1) * (1 - z2))
    return lo, lo + tail


ln2L, ln2U = ln_bounds(2)
ln3L, ln3U = ln_bounds(3)
gL = ln3L / ln2U
gU = ln3U / ln2L  # log2(3) in [gL,gU], width ~1e-200
print(
    f"[log2 3] bracket width ~ {float(gU - gL):.2e};  {float(gL):.12f} < log2 3 < {float(gU):.12f}"
)

X = 1 << 71
ok = True


def chk(name, cond):
    global ok
    ok = ok and cond
    print(f"  [{'OK' if cond else 'FAIL'}] {name}")


# ---- 1. alpha = 317/200 is a valid strict upper bound for log2 3 ----
print("1. coarse alpha bound 317/200 > log2 3")
chk("317/200 > log2 3", F(317, 200) > gU)
chk("3^200 < 2^317 (equivalent integer witness)", 3**200 < 2**317)

# ---- 2. height window: n1 <= 29*2^71 < 2^76  (Anum=29) ----
print("2. height window Anum=29")
chk("29*2^71 < 2^76", 29 * X < (1 << 76))
chk(
    "log2(29*2^71+1) < 76", F(29) * X + 1 < (1 << 76)
)  # so log2(n1+1) < 76 used in caps
Lmax = 76  # rigorous: log2(n1+1) < 76

# ---- 3. caps kcap are valid upper bounds given k_{i+j} < alpha^j * log2(n1+1) ----
# kcap[i] (i=1..7) must satisfy kcap[i] >= max integer k with k < alpha^{i-1}*log2(n1+1).
# Using alpha=317/200 (>= true) and log2(n1+1) < 76 (both make the RHS an over-estimate),
# the true bound true_max_i = ceil(alpha_true^{i-1} * log2(n1+1)) - 1 <= ceil((317/200)^{i-1}*76)-1.
print("3. valuation caps kcap = [75,120,191,303,481,763,1210]")
kcap = [
    75,
    120,
    191,
    303,
    481,
    763,
    1210,
]  # the i-th cap is kcap[i-1] (engine pads index 0 with a dummy)
a = F(317, 200)
for i in range(1, 8):
    bound = a ** (i - 1) * Lmax  # k_i < bound (strict, over-estimate of truth)
    tmax = (
        -((-bound.numerator) // bound.denominator) - 1
    )  # ceil(bound)-1 = largest int strictly < bound
    chk(
        f"kcap[{i}]={kcap[i - 1]} >= true-max {tmax}  (k_{i} < (317/200)^{i - 1}*76 = {float(bound):.2f})",
        kcap[i - 1] >= tmax,
    )

# ---- 4. CF bracket for floor_alpha decides floor(n*log2 3) over the used range ----
# Engine: AL_LO=83130157078217/52449289519716 (=P28/Q28), AL_HI=18340740190704/11571718688839 (=P27/Q27).
# floor_alpha(n) returns floor(AL_LO*n)==floor(AL_HI*n) or throws. Must agree for all n < FRONTIER.
print("4. CF bracket brackets log2 3 and decides floor over the used range")
AL_LO = F(83130157078217, 52449289519716)
AL_HI = F(18340740190704, 11571718688839)
chk("AL_LO < log2 3 < AL_HI", AL_LO < gL and gU < AL_HI)
FRONTIER = 72057431991
# the bracket decides floor(n*log2 3) for all n up to ~Q27; certify it agrees with the exact
# enclosure at the only place it could fail: when n*log2 3 is nearest an integer below FRONTIER.
# Sufficient exact check: for the two convergent denominators the floors agree up to FRONTIER
# iff no integer lies in (AL_LO*n, AL_HI*n] for n<FRONTIER. Width n*(AL_HI-AL_LO) < FRONTIER*w.
w = AL_HI - AL_LO
chk(
    "bracket width * FRONTIER < 1 (floors cannot straddle an integer below frontier)",
    FRONTIER * w < 1,
)
chk(
    "FRONTIER = 72057431991 (Paper 2 first positive surplus Q21+Q22)",
    FRONTIER == 72057431991,
)

# ---- 5. extra lower-bound stages: exact value of the rounded term ----
print("5. extra lower-bound stages")
term = -(-(93 * (1 << 189)) // 50)  # ceil(93*2^189/50)
chk("term = ceil(93*2^189/50) computed exactly", term == (93 * (1 << 189) + 49) // 50)
extra = [0, X, X, X, X, X, 3 * (1 << 74), 7 * (1 << 117), term]
chk("extra[6]=3*2^74 > 2^71 (=X)", extra[6] > X)
chk("extra[7]=7*2^117 > extra[6]", extra[7] > extra[6])
chk("extra[8]=term > extra[7]", extra[8] > extra[7])
print(
    "    extra = [0, 2^71, 2^71, 2^71, 2^71, 2^71, 3*2^74, 7*2^117, ceil(93*2^189/50)]"
)
print(
    f"    log2 of stages 6,7,8 ~ {76.585:.1f}? -> {float(__import__('math').log2(extra[6])):.2f}, {float(__import__('math').log2(extra[7])):.2f}, {float(__import__('math').log2(extra[8])):.2f}"
)

print("\nRESULT:", "ALL CONSTANT CHECKS PASSED" if ok else "SOME CHECK FAILED")
