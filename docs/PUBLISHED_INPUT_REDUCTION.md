# Published inputs and exact reduction for the `m=96` certificate

This document records the complete logical interface between the published
Collatz-cycle literature and the finite search. It is intended to make the
normalizations and constants independently auditable.

## 1. Common notation

Use the shortcut Collatz map

\[
C(n)=\begin{cases}
 n/2,&n\text{ even},\\
 (3n+1)/2,&n\text{ odd}.
\end{cases}
\]

A nontrivial `m`-cycle has exactly `m` local minima. Enumerate them cyclically
as \(n_1,\ldots,n_m\). Starting at \(n_i\), let

- \(k_i\) be the number of consecutive odd shortcut steps;
- \(\ell_i\) be the number of following even shortcut steps before
  \(n_{i+1}\);
- \(K=\sum_i k_i\) and \(L=\sum_i\ell_i\);
- \(\delta=\log_2 3\).

These are the conventions used by Hercher and by Simons--de Weger. In the C++
search, `k_i`, `ell_i`, `Ksum`, and `Lsum` have exactly these meanings. The
local minimum and quotient coordinates are

\[
 n_i=2^{k_i}a_i-1,\qquad a_i\text{ odd},
\]

and one complete block satisfies

\[
 n_{i+1}=\frac{3^{k_i}a_i-1}{2^{\ell_i}},\qquad
 \ell_i=\nu_2(3^{k_i}a_i-1),\qquad
 k_{i+1}=\nu_2(n_{i+1}+1).
\]

## 2. Published input A: the verified convergence floor

D. Barina, “Improved verification limit for the convergence of the Collatz
conjecture,” *The Journal of Supercomputing* 81 (2025), Article 810,
DOI `10.1007/s11227-025-07337-0`, reports exhaustive verification through
\(2^{71}\).

Consequently, every member of a nontrivial positive cycle satisfies

\[
 n\ge X:=2^{71}.
\]

Indeed, a cycle member below the verified threshold would have a forward orbit
entering the trivial cycle, contradicting nontrivial periodicity. In particular,
every local minimum satisfies \(n_i\ge X\).

## 3. Published input B: Hercher's lower and growth bounds

C. Hercher, “There are no Collatz m-cycles with m <= 91,” *Journal of Integer
Sequences* 26 (2023), Article 23.3.5, provides two inputs.

### 3.1 Lower bound for the odd-step total

Corollary 24 states that an `m`-cycle with \(m\le98\) has

\[
 K>7.76\times10^{19}.
\]

Therefore a hypothetical `m=96` cycle has

\[
 K>77{,}600{,}000{,}000{,}000{,}000{,}000.
\]

The exact certificate safely uses the integer lower input

\[
 K_*:=77{,}600{,}000{,}000{,}000{,}000{,}000,
\]

because the published inequality is strict.

### 3.2 Growth of successive local minima

Hercher's Lemma 20 states that successive local minima satisfy

\[
 n_{i+1}<n_i^\delta.
\]

Since \(2^{k_i}\mid n_i+1\),

\[
 k_i\le\log_2(n_i+1).
\]

Iteration of the growth inequality gives

\[
 k_{i+r}<\delta^r\log_2(n_i+1)\qquad(r\ge1).
\]

This is the only imported growth law used for the branch caps and stage lower
bounds.

## 4. Published input C: Simons--de Weger's upper bound

J. L. Simons and B. M. M. de Weger, “Theoretical and computational bounds for
m-cycles of the 3n+1 problem,” *Acta Arithmetica* 117 (2005), 51--70,
DOI `10.4064/aa117-1-3`, prove in Lemma 16 and the proof of Theorem 3(d) that,
for \(91\le m\le515{,}619\),

\[
 K<K_2(m),\qquad
 K_2(m)=k_2(m)m\delta^m,
\]

with \(k_2(m)<1.4784\). Hence for \(m=96\),

\[
 K<1.4784\cdot96\,\delta^{96}.
\]

The exact analytic verifier uses \(\delta<317/200\) and checks by integer
cross-multiplication that

\[
1.4784\cdot96\left(\frac{317}{200}\right)^{96}
<7{,}941{,}964{,}418{,}702{,}608{,}664{,}581.
\]

## 5. New exact denominator lift

A cyclic rotation can be chosen so that, for every \(1\le t\le m\),

\[
\sum_{j=m-t+1}^{m}k_j\ge\frac{tK}{m}.
\]

Combining this suffix balance with Hercher's growth law gives

\[
\log_2(n_{m-t+1}+1)
\ge
\frac{tK}{m}\frac{\delta-1}{\delta^t-1}.
\]

Inserted into the standard cycle product estimate, this gives a rational upper
bound for

\[
0<\frac{K+L}{K}-\delta.
\]

`code/m96/certify_reduction.py` evaluates the bound using exact fractions and
certified logarithm intervals. With the published lower input for `K` and the
Barina floor, the first Farey-neighbor certificate forces

\[
K\ge K_0:=205{,}632{,}218{,}873{,}398{,}596{,}256.
\]

## 6. Exhaustive finite case

The proof splits into the exhaustive alternatives

\[
 n_1\le29X\qquad\text{or}\qquad n_1>29X,
\]

where \(n_1\) is the least local minimum. The number `29` is not imported from
any paper.

In the finite case,

\[
X\le n_1\le29X,
\]

and \(29X+1<2^{76}\). Since \(2^{k_1}\mid n_1+1\), this implies

\[
1\le k_1\le75.
\]

Thus the manifest branches `k1=1,...,75` are disjoint and exhaustive.
Hercher's growth law, \(\delta<317/200\), and \(n_1+1<2^{76}\) give the safe
caps

\[
(k_1,\ldots,k_7)\le(75,120,191,303,481,763,1210).
\]

The lower bound \(K\ge K_0\), the caps already used, and suffix growth give

\[
n_6\ge3\cdot2^{74},\qquad
n_7\ge7\cdot2^{117},\qquad
n_8\ge\left\lceil\frac{93}{50}2^{189}\right\rceil.
\]

Every one of these numerical implications is rechecked in
`certificates/m96_reduction_certificate.json`.

The source-level proof in `FIXED_BRANCH_COMPLETENESS.md` shows that, for each
fixed `k1`, the search partitions the entire admissible set by the exact
values of `ell_i` and `k_{i+1}`. Therefore zero hits in all 75 branches exclude
the finite case.

## 7. Infinite complement and final contradiction

After the finite case is excluded, any hypothetical 96-cycle would have
\(n_1>29X\), and because \(n_1\) is the least local minimum, all local minima
would exceed \(29X\). Reapplying the exact denominator lift with this stronger
floor forces

\[
K\ge Q:=7{,}941{,}964{,}418{,}702{,}608{,}664{,}581.
\]

Section 4's published Simons--de Weger bound gives \(K<Q\). This contradiction
excludes `m=96`.

## 8. Logical status

Barina's, Hercher's, and Simons--de Weger's statements are published theorems
or published verified computations. They are cited inputs, not conjectural
assumptions. Once the exact analytic certificate, the 75 raw zero-hit branches,
and the branch-cover verifier all accept, the conclusion “no nontrivial
positive Collatz 96-cycle exists” is unconditional in the ordinary
mathematical sense.
