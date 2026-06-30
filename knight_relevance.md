# Relevance of Kevin Knight's "Collatz high cycles do not exist"

Knight's Discrete Mathematics paper proves that rational Collatz high cycles are not composed of positive integers. This is a clean structural fact about the extremal/high Christoffel parity vector for a fixed length and odd-count pair.

For the present `m=96` pipeline, it is useful as an external sanity constraint but does not directly replace the Hercher/Simons--de Weger branch search. The reason is that an arbitrary nontrivial integer `m`-cycle need not be the high cycle for its `(k,x)` parameters. Thus Knight's theorem can safely reject a branch only if the branch-cover analysis proves that the candidate branch realizes the high-cycle parity vector or is forced into the high-cycle extremal rotation.

Recommended use:

1. Add an optional checker that recognizes upper Christoffel/high-cycle parity vectors among generated shape branches.
2. Reject those branches immediately by citing Knight.
3. Do not use Knight to reject general branches unless the high-cycle equivalence is proven for that branch.

