#include "search_core.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace collatz {
namespace {

mpz_class floor_div(const mpz_class& a, const mpz_class& b) {
    if (b <= 0) throw std::runtime_error("floor_div denominator is not positive");
    mpz_class q;
    mpz_fdiv_q(q.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t());
    return q;
}

mpz_class ceil_div(const mpz_class& a, const mpz_class& b) {
    if (b <= 0) throw std::runtime_error("ceil_div denominator is not positive");
    mpz_class q;
    mpz_cdiv_q(q.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t());
    return q;
}

unsigned floor_log2(const mpz_class& n) {
    if (n <= 0) throw std::runtime_error("floor_log2 argument is not positive");
    return static_cast<unsigned>(mpz_sizeinbase(n.get_mpz_t(), 2) - 1);
}

unsigned valuation_two(const mpz_class& n) {
    if (n == 0) throw std::runtime_error("v2(0) is undefined");
    return static_cast<unsigned>(mpz_scan1(n.get_mpz_t(), 0));
}

mpz_class modulo_power_two(const mpz_class& value, unsigned bits) {
    mpz_class result;
    mpz_fdiv_r_2exp(result.get_mpz_t(), value.get_mpz_t(), bits);
    return result;
}

u64 checked_add(u64 left, u64 right, const char* label) {
    if (right > std::numeric_limits<u64>::max() - left) {
        throw std::runtime_error(std::string(label) + " overflow");
    }
    return left + right;
}

struct Live {
    mpz_class lower;
    mpz_class upper;
    mpz_class residue;
    unsigned bits = 0;
    bool valid = true;
};

bool normalize(Live& state) {
    if (!state.valid || state.lower > state.upper) {
        state.valid = false;
        return false;
    }
    state.residue = modulo_power_two(state.residue, state.bits);
    const mpz_class modulus = mpz_class(1) << state.bits;
    const mpz_class first =
        state.residue + ceil_div(state.lower - state.residue, modulus) * modulus;
    if (first > state.upper) {
        state.valid = false;
        return false;
    }
    const mpz_class last =
        state.residue + floor_div(state.upper - state.residue, modulus) * modulus;
    state.lower = first;
    state.upper = last;
    if (modulo_power_two(state.lower - state.residue, state.bits) != 0 ||
        modulo_power_two(state.upper - state.residue, state.bits) != 0) {
        throw std::runtime_error("normalized progression endpoint invariant failed");
    }
    return true;
}

bool intersect_interval(Live& state, const mpz_class* lower, const mpz_class* upper) {
    if (lower != nullptr && *lower > state.lower) state.lower = *lower;
    if (upper != nullptr && *upper < state.upper) state.upper = *upper;
    return normalize(state);
}

bool intersect_linear_congruence(
    Live& state,
    const mpz_class& coefficient,
    const mpz_class& rhs,
    unsigned new_bits
) {
    if (new_bits <= state.bits) {
        if (modulo_power_two(coefficient * state.residue - rhs, new_bits) != 0) {
            state.valid = false;
            return false;
        }
        return true;
    }
    const mpz_class difference = modulo_power_two(rhs - coefficient * state.residue, new_bits);
    if (modulo_power_two(difference, state.bits) != 0) {
        state.valid = false;
        return false;
    }
    const unsigned extra_bits = new_bits - state.bits;
    const mpz_class reduced_rhs = difference >> state.bits;
    const mpz_class reduced_coefficient = modulo_power_two(coefficient, extra_bits);
    const mpz_class modulus = mpz_class(1) << extra_bits;
    mpz_class inverse;
    if (mpz_invert(
            inverse.get_mpz_t(), reduced_coefficient.get_mpz_t(), modulus.get_mpz_t()
        ) == 0) {
        state.valid = false;
        return false;
    }
    const mpz_class lift = modulo_power_two(reduced_rhs * inverse, extra_bits);
    state.residue += lift << state.bits;
    state.bits = new_bits;
    return normalize(state);
}

class Search {
  public:
    Search(
        const CaseConfig& config,
        const WorkUnit& unit,
        u64 enum_threshold,
        FaultMode fault,
        bool debug_terminal_dump
    )
        : config_(config),
          unit_(unit),
          enum_threshold_(enum_threshold),
          fault_(fault),
          debug_terminal_dump_(debug_terminal_dump) {
        counters_.level_nodes.resize(static_cast<std::size_t>(config.depth + 1));
        powers_three_.push_back(1);
    }

    SearchResult run() {
        if (enum_threshold_ == 0) throw std::runtime_error("enum threshold must be positive");
        const mpz_class count = unit_.index_end - unit_.index_start + 1;
        if (unit_.root_count == 0) {
            return {counters_, 0, {}};
        }
        Live root{
            unit_.root_first + 2 * unit_.index_start,
            unit_.root_first + 2 * unit_.index_end,
            1,
            1,
            true,
        };
        if (!normalize(root)) throw std::runtime_error("nonempty work unit normalized to empty");
        recurse(1, unit_.k1, unit_.k1, unit_.k1, 0, 1, 0, 0, root);
        return {counters_, count, terminal_decisions_};
    }

  private:
    const CaseConfig& config_;
    const WorkUnit& unit_;
    u64 enum_threshold_;
    SearchCounters counters_;
    std::vector<mpz_class> powers_three_;
    FaultMode fault_ = FaultMode::None;
    bool fault_injected_ = false;
    bool debug_terminal_dump_ = false;
    std::vector<std::pair<std::string, std::string>> terminal_decisions_;

    const mpz_class& power_three(unsigned exponent) {
        while (powers_three_.size() <= exponent) {
            powers_three_.push_back(powers_three_.back() * 3);
        }
        return powers_three_[exponent];
    }

    void observe(const mpz_class& value) {
        if (value == 0) return;
        mpz_class magnitude = value >= 0 ? value : -value;
        const u64 bits = static_cast<u64>(mpz_sizeinbase(magnitude.get_mpz_t(), 2));
        counters_.max_integer_bits = std::max(counters_.max_integer_bits, bits);
    }

    u64 floor_alpha(u64 value) {
        const mpz_class n(std::to_string(value));
        const mpz_class lower = floor_div(config_.alpha_lower_num * n, config_.alpha_lower_den);
        const mpz_class upper = floor_div(config_.alpha_upper_num * n, config_.alpha_upper_den);
        if (lower != upper) throw std::runtime_error("alpha bracket leaves an undecided floor");
        if (!lower.fits_ulong_p()) throw std::runtime_error("floor_alpha does not fit unsigned long");
        u64 result = static_cast<u64>(lower.get_ui());
        if (fault_ == FaultMode::ChangeFloorAlpha && !fault_injected_) {
            fault_injected_ = true;
            result = checked_add(result, 1, "faulted floor alpha");
        }
        return result;
    }

    std::pair<mpz_class, mpz_class> n_range(
        const Live& live,
        const mpz_class& p,
        const mpz_class& q,
        unsigned shift,
        unsigned k
    ) {
        const mpz_class power_two = mpz_class(1) << k;
        const mpz_class denominator = mpz_class(1) << shift;
        return {
            (power_two * (p * live.lower + q) - denominator) >> shift,
            (power_two * (p * live.upper + q) - denominator) >> shift,
        };
    }

    bool linear_ge(Live& live, const mpz_class& coefficient, const mpz_class& constant) {
        if (coefficient > 0) {
            const mpz_class lower = ceil_div(-constant, coefficient);
            return intersect_interval(live, &lower, nullptr);
        }
        if (coefficient < 0) {
            const mpz_class upper = floor_div(constant, -coefficient);
            return intersect_interval(live, nullptr, &upper);
        }
        if (constant < 0) {
            live.valid = false;
            return false;
        }
        return true;
    }

    u64 live_count_capped(const Live& live) const {
        const mpz_class count =
            (live.upper - live.lower) / (mpz_class(1) << live.bits) + 1;
        const mpz_class cap(std::to_string(enum_threshold_));
        if (count > cap) return enum_threshold_ + 1;
        if (!count.fits_ulong_p()) throw std::runtime_error("live count conversion failed");
        return static_cast<u64>(count.get_ui());
    }

    mpz_class live_count_exact(const Live& live) const {
        return (live.upper - live.lower) / (mpz_class(1) << live.bits) + 1;
    }

    void assert_state(
        const Live& live,
        const mpz_class& p,
        const mpz_class& q,
        unsigned shift
    ) {
        if (!live.valid || live.lower > live.upper) throw std::runtime_error("invalid live state");
        if (live.residue != modulo_power_two(live.residue, live.bits)) {
            throw std::runtime_error("noncanonical progression residue");
        }
        if (modulo_power_two(live.lower - live.residue, live.bits) != 0 ||
            modulo_power_two(live.upper - live.residue, live.bits) != 0) {
            throw std::runtime_error("progression endpoint congruence failed");
        }
        if (!mpz_odd_p(p.get_mpz_t())) throw std::runtime_error("affine coefficient is even");
        if (modulo_power_two(p * live.residue + q, shift) != 0) {
            throw std::runtime_error("affine divisibility invariant failed");
        }
        const mpz_class representative = (p * live.residue + q) >> shift;
        if (!mpz_odd_p(representative.get_mpz_t())) {
            throw std::runtime_error("represented local minimum is even");
        }
    }

    void deterministic_finish(
        int level,
        unsigned k1,
        unsigned k,
        u64 k_sum,
        u64 l_sum,
        const mpz_class& p,
        const mpz_class& q,
        unsigned shift,
        const Live& live
    ) {
        const mpz_class step = mpz_class(1) << live.bits;
        mpz_class visited = 0;
        for (mpz_class a = live.lower; a <= live.upper; a += step) {
            if (fault_ == FaultMode::OmitFirstA1 && !fault_injected_) {
                fault_injected_ = true;
                continue;
            }
            ++visited;
            counters_.deterministic_values = checked_add(
                counters_.deterministic_values, 1, "deterministic value count"
            );
            const mpz_class numerator = p * a + q;
            if (modulo_power_two(numerator, shift) != 0) {
                throw std::runtime_error("nonintegral deterministic affine state");
            }
            mpz_class ai = numerator >> shift;
            if (!mpz_odd_p(ai.get_mpz_t())) throw std::runtime_error("even deterministic state");
            unsigned current_k = k;
            u64 current_k_sum = k_sum;
            u64 current_l_sum = l_sum;
            const mpz_class n1 = (a << k1) - 1;
            std::string terminal_reason;
            for (int index = level; index <= config_.depth; ++index) {
                counters_.deterministic_nodes = checked_add(
                    counters_.deterministic_nodes, 1, "deterministic node count"
                );
                const mpz_class value = ai * power_three(current_k) - 1;
                const unsigned ell = valuation_two(value);
                const mpz_class next_n = value >> ell;
                mpz_class required = std::max(
                    config_.stage_minima.at(static_cast<std::size_t>(index)),
                    std::max(config_.x, n1)
                );
                if (fault_ == FaultMode::WeakenMinimum && !fault_injected_) {
                    fault_injected_ = true;
                    --required;
                }
                if (next_n < required) {
                    terminal_reason = "STAGE_MINIMUM";
                    break;
                }
                const u64 next_l_sum = checked_add(current_l_sum, ell, "L sum");
                if (current_k_sum >= config_.first_positive_surplus) {
                    throw std::runtime_error("prefix beyond certified A28 gate");
                }
                if (checked_add(current_k_sum, next_l_sum, "prefix sum") >
                    floor_alpha(current_k_sum)) {
                    counters_.prefix_prunes = checked_add(
                        counters_.prefix_prunes, 1, "prefix prune count"
                    );
                    terminal_reason = "PREFIX_GATE";
                    break;
                }
                if (index == config_.depth) {
                    counters_.hits = checked_add(counters_.hits, 1, "hit count");
                    terminal_reason = "SURVIVOR";
                    break;
                }
                const unsigned next_k = valuation_two(next_n + 1);
                if (next_k < 1 ||
                    next_k > config_.k_caps.at(static_cast<std::size_t>(index))) {
                    terminal_reason = "CAP";
                    break;
                }
                ai = (next_n + 1) >> next_k;
                if (!mpz_odd_p(ai.get_mpz_t())) throw std::runtime_error("next a is even");
                current_k = next_k;
                current_k_sum = checked_add(current_k_sum, next_k, "K sum");
                current_l_sum = next_l_sum;
            }
            if (terminal_reason.empty()) {
                throw std::runtime_error("deterministic value has no terminal reason");
            }
            if (debug_terminal_dump_) {
                terminal_decisions_.emplace_back(a.get_str(), terminal_reason);
            }
        }
        if (visited != live_count_exact(live)) {
            throw std::runtime_error("deterministic iteration did not cover progression");
        }
    }

    void recurse(
        int level,
        unsigned k1,
        unsigned k,
        u64 k_sum,
        u64 l_sum,
        const mpz_class& p,
        const mpz_class& q,
        unsigned shift,
        const Live& live
    ) {
        assert_state(live, p, q, shift);
        counters_.recursive_nodes = checked_add(counters_.recursive_nodes, 1, "node count");
        observe(live.lower);
        observe(live.upper);
        observe(p);
        observe(q);
        if (live_count_capped(live) <= enum_threshold_) {
            deterministic_finish(level, k1, k, k_sum, l_sum, p, q, shift, live);
            return;
        }

        const auto range = n_range(live, p, q, shift, k);
        const mpz_class n1_min = (live.lower << k1) - 1;
        const mpz_class extra = config_.stage_minima.at(static_cast<std::size_t>(level));
        mpz_class lower_bound = std::max(extra, std::max(config_.x, n1_min));
        if (fault_ == FaultMode::WeakenMinimum && !fault_injected_) {
            fault_injected_ = true;
            --lower_bound;
        }
        const mpz_class power_k = power_three(k);
        const mpz_class two_k = mpz_class(1) << k;
        const mpz_class limit =
            (power_k * (range.second + 1) - two_k) / (two_k * lower_bound);
        if (limit < 2) {
            counters_.bound_prunes = checked_add(counters_.bound_prunes, 1, "bound prune count");
            return;
        }
        const unsigned ell_max = floor_log2(limit);
        for (unsigned ell = 1; ell <= ell_max; ++ell) {
            if (fault_ == FaultMode::SkipFirstEll && !fault_injected_) {
                fault_injected_ = true;
                continue;
            }
            const u64 next_l_sum = checked_add(l_sum, ell, "L sum");
            if (k_sum >= config_.first_positive_surplus) {
                throw std::runtime_error("prefix beyond certified A28 gate");
            }
            if (checked_add(k_sum, next_l_sum, "prefix sum") > floor_alpha(k_sum)) {
                counters_.prefix_prunes = checked_add(
                    counters_.prefix_prunes, 1, "prefix prune count"
                );
                continue;
            }
            Live branch = live;
            const mpz_class denominator = power_k * p;
            const mpz_class lower = ceil_div(
                extra * (mpz_class(1) << (shift + ell)) + (mpz_class(1) << shift) -
                    power_k * q,
                denominator
            );
            if (!intersect_interval(branch, &lower, nullptr)) continue;
            const mpz_class coefficient =
                power_k * p - (mpz_class(1) << (k1 + shift + ell));
            const mpz_class constant =
                power_k * q - (mpz_class(1) << shift) + (mpz_class(1) << (shift + ell));
            if (!linear_ge(branch, coefficient, constant)) continue;
            const mpz_class n_max =
                (power_k * (p * branch.upper + q) - (mpz_class(1) << shift)) >>
                (shift + ell);
            if (level == config_.depth) {
                counters_.final_intervals = checked_add(
                    counters_.final_intervals, 1, "final interval count"
                );
                const unsigned bits = shift + ell + 1;
                const mpz_class rhs = (mpz_class(1) << (shift + ell)) +
                    (mpz_class(1) << shift) - power_k * q;
                if (intersect_linear_congruence(branch, power_k * p, rhs, bits)) {
                    counters_.hits = checked_add(counters_.hits, 1, "hit count");
                }
                continue;
            }

            const int k_max = std::min<int>(
                static_cast<int>(floor_log2(n_max + 1)),
                static_cast<int>(config_.k_caps.at(static_cast<std::size_t>(level)))
            );
            const mpz_class p2 = power_k * p;
            const mpz_class q_base =
                power_k * q + ((mpz_class(1) << ell) - 1) * (mpz_class(1) << shift);
            const unsigned base_exponent = shift + ell;
            unsigned exponent = base_exponent + 1;
            Live continuation = branch;
            if (!intersect_linear_congruence(continuation, p2, -q_base, exponent)) continue;
            for (int next_k = 1;
                 next_k <= k_max && continuation.valid;
                 ++next_k, ++exponent) {
                if (continuation.bits != exponent) {
                    throw std::runtime_error("unexpected Hensel precision");
                }
                const mpz_class representative = p2 * continuation.residue + q_base;
                bool bit = mpz_tstbit(representative.get_mpz_t(), exponent) != 0;
                if (fault_ == FaultMode::ReverseHenselChild && !fault_injected_) {
                    fault_injected_ = true;
                    bit = !bit;
                }
                Live exact = continuation;
                Live next = continuation;
                exact.bits = exponent + 1;
                next.bits = exponent + 1;
                if (!bit) {
                    exact.residue += mpz_class(1) << exponent;
                } else {
                    next.residue += mpz_class(1) << exponent;
                }
                const bool exact_ok = normalize(exact);
                const bool next_ok = normalize(next);
                mpz_class child_count = 0;
                if (exact_ok) child_count += live_count_exact(exact);
                if (next_ok) child_count += live_count_exact(next);
                if (child_count != live_count_exact(continuation)) {
                    throw std::runtime_error("Hensel children do not exactly cover parent");
                }
                if (exact_ok) {
                    const mpz_class exact_value = p2 * exact.residue + q_base;
                    if (modulo_power_two(exact_value, exponent) != 0 ||
                        !mpz_tstbit(exact_value.get_mpz_t(), exponent)) {
                        throw std::runtime_error("Hensel exact child has wrong valuation");
                    }
                }
                if (next_ok &&
                    modulo_power_two(p2 * next.residue + q_base, exponent + 1) != 0) {
                    throw std::runtime_error("Hensel continuation child is not divisible");
                }
                if (exact_ok) {
                    const unsigned new_shift = exponent;
                    counters_.level_nodes.at(static_cast<std::size_t>(level)) = checked_add(
                        counters_.level_nodes.at(static_cast<std::size_t>(level)),
                        1,
                        "level count"
                    );
                    recurse(
                        level + 1,
                        k1,
                        static_cast<unsigned>(next_k),
                        checked_add(k_sum, static_cast<u64>(next_k), "K sum"),
                        next_l_sum,
                        p2,
                        q_base,
                        new_shift,
                        exact
                    );
                }
                if (!next_ok) break;
                continuation = std::move(next);
            }
        }
    }
};

}  // namespace

SearchResult search_unit(
    const CaseConfig& config,
    const WorkUnit& unit,
    u64 enum_threshold,
    FaultMode fault,
    bool debug_terminal_dump
) {
    return Search(
        config,
        unit,
        enum_threshold,
        fault,
        debug_terminal_dump
    ).run();
}

}  // namespace collatz
