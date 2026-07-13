#include "search_core.hpp"

#include <nlohmann/json.hpp>
#include <openssl/evp.h>

#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unistd.h>

#ifndef COLLATZ_PROVER_SOURCE_SHA256
#error "COLLATZ_PROVER_SOURCE_SHA256 must be supplied by the build"
#endif

namespace fs = std::filesystem;
using json = nlohmann::json;
using collatz::CaseConfig;
using collatz::FaultMode;
using collatz::SearchResult;
using collatz::WorkUnit;
using collatz::u64;

namespace {

std::string read_file(const fs::path& path) {
    if (fs::is_symlink(path) || !fs::is_regular_file(path)) {
        throw std::runtime_error("input is not a regular file: " + path.string());
    }
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open input: " + path.string());
    std::ostringstream content;
    content << input.rdbuf();
    return content.str();
}

json read_canonical_json(const fs::path& path) {
    const std::string raw = read_file(path);
    const json value = json::parse(raw);
    if (raw != value.dump() + "\n") {
        throw std::runtime_error("input JSON is not canonical: " + path.string());
    }
    return value;
}

std::string sha256_bytes(const std::string& payload) {
    EVP_MD_CTX* context = EVP_MD_CTX_new();
    if (context == nullptr) throw std::runtime_error("cannot allocate SHA-256 context");
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int length = 0;
    const bool ok = EVP_DigestInit_ex(context, EVP_sha256(), nullptr) == 1 &&
        EVP_DigestUpdate(context, payload.data(), payload.size()) == 1 &&
        EVP_DigestFinal_ex(context, digest, &length) == 1;
    EVP_MD_CTX_free(context);
    if (!ok || length != 32) throw std::runtime_error("SHA-256 failure");
    static constexpr char hex[] = "0123456789abcdef";
    std::string result;
    result.reserve(64);
    for (unsigned index = 0; index < length; ++index) {
        result.push_back(hex[digest[index] >> 4]);
        result.push_back(hex[digest[index] & 15]);
    }
    return result;
}

std::string sha256_file(const fs::path& path) { return sha256_bytes(read_file(path)); }

std::string object_id(const std::string& domain, const json& value) {
    return sha256_bytes(domain + std::string(1, '\0') + value.dump());
}

void exact_keys(const json& value, std::initializer_list<const char*> expected, const char* label) {
    if (!value.is_object()) throw std::runtime_error(std::string(label) + " is not an object");
    std::map<std::string, bool> keys;
    for (const char* key : expected) keys.emplace(key, true);
    if (value.size() != keys.size()) throw std::runtime_error(std::string(label) + " key count mismatch");
    for (auto iterator = value.begin(); iterator != value.end(); ++iterator) {
        if (keys.count(iterator.key()) == 0) {
            throw std::runtime_error(std::string(label) + " has unexpected key " + iterator.key());
        }
    }
}

bool canonical_nat(const std::string& value, bool positive) {
    if (value.empty() || (value.size() > 1 && value.front() == '0')) return false;
    for (const char character : value) {
        if (character < '0' || character > '9') return false;
    }
    return !positive || value != "0";
}

std::string decimal(const json& object, const char* key, bool positive = false) {
    if (!object.contains(key) || !object.at(key).is_string()) {
        throw std::runtime_error(std::string("missing decimal string: ") + key);
    }
    const std::string value = object.at(key).get<std::string>();
    if (!canonical_nat(value, positive)) {
        throw std::runtime_error(std::string("noncanonical decimal string: ") + key);
    }
    return value;
}

u64 small_nat(const json& object, const char* key, bool positive = false) {
    const std::string value = decimal(object, key, positive);
    std::size_t consumed = 0;
    const unsigned long long parsed = std::stoull(value, &consumed);
    if (consumed != value.size()) throw std::runtime_error("small integer parse failed");
    return static_cast<u64>(parsed);
}

mpz_class big_nat(const json& object, const char* key, bool positive = false) {
    return mpz_class(decimal(object, key, positive));
}

std::string require_hash(const json& object, const char* key) {
    const std::string value = object.at(key).get<std::string>();
    if (value.size() != 64 || value.find_first_not_of("0123456789abcdef") != std::string::npos) {
        throw std::runtime_error(std::string("invalid SHA-256: ") + key);
    }
    return value;
}

CaseConfig parse_config(
    const json& value,
    const std::string& math_hash,
    const json& math_certificate
) {
    exact_keys(
        value,
        {"X", "alpha_bracket", "depth", "first_positive_surplus", "k1_range", "k_caps",
         "m", "math_certificate_sha256", "schema", "stage_minima", "window"},
        "case config"
    );
    if (value.at("schema") != "collatz.case-config.v1") throw std::runtime_error("config schema mismatch");
    CaseConfig config;
    config.m = static_cast<int>(small_nat(value, "m", true));
    if (config.m < 92 || config.m > 96) throw std::runtime_error("unsupported case");
    config.x = big_nat(value, "X", true);
    config.depth = static_cast<int>(small_nat(value, "depth", true));
    config.first_positive_surplus = small_nat(value, "first_positive_surplus", true);
    config.math_certificate_sha256 = require_hash(value, "math_certificate_sha256");
    if (config.math_certificate_sha256 != math_hash) throw std::runtime_error("math certificate hash mismatch");
    if (!math_certificate.is_object() ||
        math_certificate.value("schema", "") != "collatz.mathematical-reductions.v1" ||
        !math_certificate.contains("case_certificates") ||
        !math_certificate.at("case_certificates").is_array()) {
        throw std::runtime_error("mathematical certificate schema mismatch");
    }
    json expected_semantics;
    for (const json& record : math_certificate.at("case_certificates")) {
        if (record.is_object() && record.value("case", "") == std::to_string(config.m)) {
            expected_semantics = record.at("search_config");
        }
    }
    json actual_semantics = value;
    actual_semantics.erase("math_certificate_sha256");
    if (expected_semantics.is_null() || actual_semantics != expected_semantics) {
        throw std::runtime_error("config semantics do not match mathematical certificate");
    }
    const json& window = value.at("window");
    exact_keys(window, {"denominator", "numerator"}, "window");
    config.window_num = big_nat(window, "numerator", true);
    config.window_den = big_nat(window, "denominator", true);
    const json& range = value.at("k1_range");
    exact_keys(range, {"max", "min"}, "k1 range");
    config.k1_min = static_cast<int>(small_nat(range, "min", true));
    config.k1_max = static_cast<int>(small_nat(range, "max", true));
    const json& alpha = value.at("alpha_bracket");
    exact_keys(alpha, {"lower_den", "lower_num", "upper_den", "upper_num"}, "alpha bracket");
    config.alpha_lower_num = big_nat(alpha, "lower_num", true);
    config.alpha_lower_den = big_nat(alpha, "lower_den", true);
    config.alpha_upper_num = big_nat(alpha, "upper_num", true);
    config.alpha_upper_den = big_nat(alpha, "upper_den", true);
    if (!value.at("k_caps").is_array() || !value.at("stage_minima").is_array()) {
        throw std::runtime_error("config arrays missing");
    }
    for (const json& item : value.at("k_caps")) {
        const json holder = {{"value", item}};
        config.k_caps.push_back(static_cast<unsigned>(small_nat(holder, "value", true)));
    }
    for (const json& item : value.at("stage_minima")) {
        const json holder = {{"value", item}};
        config.stage_minima.push_back(big_nat(holder, "value", true));
    }
    if (config.k_caps.size() != static_cast<std::size_t>(config.depth) ||
        config.stage_minima.size() != static_cast<std::size_t>(config.depth + 1)) {
        throw std::runtime_error("config array dimensions mismatch");
    }
    config.config_id = object_id("collatz.case-config.v1", value);
    return config;
}

WorkUnit parse_unit(const json& value, const CaseConfig& config) {
    exact_keys(value, {"config_id", "index_range", "k1", "m", "root", "schema", "unit_id"}, "work unit");
    if (value.at("schema") != "collatz.work-unit.v1") throw std::runtime_error("unit schema mismatch");
    json identity = value;
    const std::string claimed_id = require_hash(value, "unit_id");
    identity.erase("unit_id");
    if (claimed_id != object_id("collatz.work-unit.v1", identity)) {
        throw std::runtime_error("unit ID mismatch");
    }
    WorkUnit unit;
    unit.unit_id = claimed_id;
    unit.config_id = require_hash(value, "config_id");
    unit.m = static_cast<int>(small_nat(value, "m", true));
    unit.k1 = static_cast<unsigned>(small_nat(value, "k1", true));
    if (unit.config_id != config.config_id || unit.m != config.m ||
        unit.k1 < static_cast<unsigned>(config.k1_min) ||
        unit.k1 > static_cast<unsigned>(config.k1_max)) {
        throw std::runtime_error("unit/config mismatch");
    }
    const json& root = value.at("root");
    exact_keys(root, {"bits", "count", "first", "last", "residue"}, "unit root");
    if (decimal(root, "bits") != "1" || decimal(root, "residue") != "1") {
        throw std::runtime_error("root progression is not odd");
    }
    unit.root_first = big_nat(root, "first");
    unit.root_last = big_nat(root, "last");
    unit.root_count = big_nat(root, "count");
    const mpz_class n1_max = config.window_num * config.x / config.window_den;
    const mpz_class divisor = mpz_class(1) << unit.k1;
    mpz_class lower;
    const mpz_class lower_numerator = config.x + 1;
    mpz_cdiv_q(lower.get_mpz_t(), lower_numerator.get_mpz_t(), divisor.get_mpz_t());
    const mpz_class upper = (n1_max + 1) / divisor;
    const mpz_class first = mpz_even_p(lower.get_mpz_t()) ? lower + 1 : lower;
    const mpz_class last = mpz_even_p(upper.get_mpz_t()) ? upper - 1 : upper;
    const mpz_class count = first > last ? mpz_class(0) : mpz_class((last - first) / 2 + 1);
    if (unit.root_first != first || unit.root_last != (count == 0 ? first - 2 : last) ||
        unit.root_count != count) {
        throw std::runtime_error("unit root is not derived from config");
    }
    const json& range = value.at("index_range");
    exact_keys(range, {"end", "start"}, "index range");
    unit.index_start = big_nat(range, "start");
    unit.index_end = big_nat(range, "end");
    if (count == 0 || unit.index_start > unit.index_end || unit.index_end >= count) {
        throw std::runtime_error("invalid nonempty unit index range");
    }
    return unit;
}

json counters_json(const SearchResult& result) {
    json counters = {
        {"bound_prunes", std::to_string(result.counters.bound_prunes)},
        {"deterministic_nodes", std::to_string(result.counters.deterministic_nodes)},
        {"deterministic_values", std::to_string(result.counters.deterministic_values)},
        {"final_intervals", std::to_string(result.counters.final_intervals)},
        {"prefix_prunes", std::to_string(result.counters.prefix_prunes)},
        {"recursive_nodes", std::to_string(result.counters.recursive_nodes)},
        {"represented_input_count", result.represented_input_count.get_str()},
    };
    for (std::size_t index = 1; index < result.counters.level_nodes.size(); ++index) {
        counters["level_" + std::to_string(index)] =
            std::to_string(result.counters.level_nodes[index]);
    }
    return counters;
}

void atomic_write(const fs::path& output, const json& value) {
    fs::create_directories(output.parent_path());
    const fs::path temporary = output.string() + ".tmp." + std::to_string(::getpid());
    {
        std::ofstream stream(temporary, std::ios::binary | std::ios::trunc);
        if (!stream) throw std::runtime_error("cannot create temporary output");
        stream << value.dump() << '\n';
        stream.flush();
        if (!stream) throw std::runtime_error("cannot write temporary output");
    }
    fs::rename(temporary, output);
}

struct Arguments {
    fs::path config;
    fs::path unit;
    fs::path output;
    fs::path math_certificate = "certificates/analytic/m92_96_reductions.json";
    u64 enum_threshold = 256;
    FaultMode fault = FaultMode::None;
    std::string fault_name;
    bool fault_false_hit = false;
    fs::path debug_terminal_dump;
};

Arguments parse_arguments(int argc, char** argv) {
    if (argc < 2 || std::string(argv[1]) != "search-unit") {
        throw std::runtime_error(
            "usage: collatz_prover search-unit --config FILE --unit FILE --output FILE "
            "[--math-certificate FILE] [--enum-threshold N]"
        );
    }
    Arguments result;
    for (int index = 2; index < argc; index += 2) {
        if (index + 1 >= argc) throw std::runtime_error("missing option value");
        const std::string option = argv[index];
        const std::string value = argv[index + 1];
        if (option == "--config") result.config = value;
        else if (option == "--unit") result.unit = value;
        else if (option == "--output") result.output = value;
        else if (option == "--math-certificate") result.math_certificate = value;
        else if (option == "--enum-threshold") result.enum_threshold = std::stoull(value);
        else if (option == "--debug-terminal-dump") result.debug_terminal_dump = value;
#ifdef COLLATZ_ENABLE_FAULT_INJECTION
        else if (option == "--fault") {
            result.fault_name = value;
            if (value == "skip-first-ell") result.fault = FaultMode::SkipFirstEll;
            else if (value == "reverse-hensel-child") {
                result.fault = FaultMode::ReverseHenselChild;
            } else if (value == "omit-first-a1") result.fault = FaultMode::OmitFirstA1;
            else if (value == "weaken-minimum") result.fault = FaultMode::WeakenMinimum;
            else if (value == "change-floor-alpha") {
                result.fault = FaultMode::ChangeFloorAlpha;
            } else if (value == "report-false-hit") {
                result.fault_false_hit = true;
            } else {
                throw std::runtime_error("unknown fault: " + value);
            }
        }
#endif
        else throw std::runtime_error("unknown option: " + option);
    }
    if (result.config.empty() || result.unit.empty() || result.output.empty()) {
        throw std::runtime_error("--config, --unit and --output are required");
    }
    return result;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Arguments arguments = parse_arguments(argc, argv);
        const std::string math_hash = sha256_file(arguments.math_certificate);
        const json math_json = read_canonical_json(arguments.math_certificate);
        const json config_json = read_canonical_json(arguments.config);
        const CaseConfig config = parse_config(config_json, math_hash, math_json);
        const json unit_json = read_canonical_json(arguments.unit);
        const WorkUnit unit = parse_unit(unit_json, config);
        const SearchResult search = collatz::search_unit(
            config,
            unit,
            arguments.enum_threshold,
            arguments.fault,
            !arguments.debug_terminal_dump.empty()
        );
        if (!arguments.debug_terminal_dump.empty()) {
            const mpz_class debug_limit = 10000;
            const mpz_class threshold(std::to_string(arguments.enum_threshold));
            if (search.represented_input_count > debug_limit ||
                search.represented_input_count > threshold ||
                search.terminal_decisions.size() !=
                    search.represented_input_count.get_ui()) {
                throw std::runtime_error(
                    "debug terminal dump requires at most min(enum-threshold,10000) values"
                );
            }
            json decisions = json::array();
            for (const auto& decision : search.terminal_decisions) {
                decisions.push_back({
                    {"a1", decision.first},
                    {"outcome", decision.second},
                });
            }
            atomic_write(
                arguments.debug_terminal_dump,
                {
                    {"decisions", decisions},
                    {"schema", "collatz.terminal-dump.v1"},
                    {"unit_id", unit.unit_id},
                }
            );
        }
        const fs::path executable = fs::canonical("/proc/self/exe");
        json semantic_parameters = {
            {"enum_threshold", std::to_string(arguments.enum_threshold)}
        };
        if (!arguments.fault_name.empty()) {
            semantic_parameters["development_fault"] = arguments.fault_name;
        }
        const u64 reported_hits = arguments.fault_false_hit
            ? search.counters.hits + 1
            : search.counters.hits;
        json result = {
            {"binary_sha256", sha256_file(executable)},
            {"config_id", config.config_id},
            {"counters", counters_json(search)},
            {"engine", "cpp-gmp-prover"},
            {"hits", std::to_string(reported_hits)},
            {"math_certificate_sha256", config.math_certificate_sha256},
            {"max_integer_bits", std::to_string(search.counters.max_integer_bits)},
            {"outcome", reported_hits == 0 ? "NO_SURVIVOR" : "SURVIVOR"},
            {"schema", "collatz.engine-result.v1"},
            {"semantic_parameters", semantic_parameters},
            {"source_sha256", COLLATZ_PROVER_SOURCE_SHA256},
            {"unit_id", unit.unit_id},
        };
        result["result_id"] = object_id("collatz.engine-result.v1", result);
        atomic_write(arguments.output, result);
        std::cout << result.dump() << '\n';
        return reported_hits == 0 ? 0 : 1;
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 2;
    }
}
