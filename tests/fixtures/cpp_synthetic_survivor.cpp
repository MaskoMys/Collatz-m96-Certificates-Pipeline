#include "../../src/prover/search_core.hpp"

#include <iostream>

int main() {
    collatz::CaseConfig config;
    config.m = 92;
    config.x = 1;
    config.window_num = 1;
    config.window_den = 1;
    config.depth = 1;
    config.k1_min = 1;
    config.k1_max = 1;
    config.k_caps = {1};
    config.stage_minima = {1, 1};
    config.alpha_lower_num = 100;
    config.alpha_lower_den = 1;
    config.alpha_upper_num = 100;
    config.alpha_upper_den = 1;
    config.first_positive_surplus = 1000;
    config.config_id = "synthetic";

    collatz::WorkUnit unit;
    unit.config_id = "synthetic";
    unit.m = 92;
    unit.k1 = 1;
    unit.root_first = 1;
    unit.root_last = 1;
    unit.root_count = 1;
    unit.index_start = 0;
    unit.index_end = 0;

    const collatz::SearchResult result = collatz::search_unit(config, unit, 256);
    if (result.counters.hits != 1) {
        std::cerr << "expected exactly one synthetic survivor, got "
                  << result.counters.hits << '\n';
        return 1;
    }
    std::cout << "SYNTHETIC_SURVIVOR_DETECTED\n";
    return 0;
}
