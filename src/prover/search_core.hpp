#pragma once

#include <gmpxx.h>

#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace collatz {

using u64 = std::uint64_t;

struct CaseConfig {
    int m = 0;
    mpz_class x;
    mpz_class window_num;
    mpz_class window_den;
    int depth = 0;
    int k1_min = 0;
    int k1_max = 0;
    std::vector<unsigned> k_caps;
    std::vector<mpz_class> stage_minima;
    mpz_class alpha_lower_num;
    mpz_class alpha_lower_den;
    mpz_class alpha_upper_num;
    mpz_class alpha_upper_den;
    u64 first_positive_surplus = 0;
    std::string math_certificate_sha256;
    std::string config_id;
};

struct WorkUnit {
    std::string unit_id;
    std::string config_id;
    int m = 0;
    unsigned k1 = 0;
    mpz_class root_first;
    mpz_class root_last;
    mpz_class root_count;
    mpz_class index_start;
    mpz_class index_end;
};

struct SearchCounters {
    u64 recursive_nodes = 0;
    u64 final_intervals = 0;
    u64 hits = 0;
    u64 prefix_prunes = 0;
    u64 deterministic_values = 0;
    u64 deterministic_nodes = 0;
    u64 bound_prunes = 0;
    u64 max_integer_bits = 0;
    std::vector<u64> level_nodes;
};

struct SearchResult {
    SearchCounters counters;
    mpz_class represented_input_count;
    std::vector<std::pair<std::string, std::string>> terminal_decisions;
};

enum class FaultMode {
    None,
    SkipFirstEll,
    ReverseHenselChild,
    OmitFirstA1,
    WeakenMinimum,
    ChangeFloorAlpha,
};

SearchResult search_unit(
    const CaseConfig& config,
    const WorkUnit& unit,
    u64 enum_threshold,
    FaultMode fault = FaultMode::None,
    bool debug_terminal_dump = false
);

}  // namespace collatz
