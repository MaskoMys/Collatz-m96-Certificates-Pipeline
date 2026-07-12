#include <cstdint>
#include <iostream>
#include <string>

using u64 = std::uint64_t;
using u128 = unsigned __int128;

static constexpr u64 P = 683381996816440ULL;
static constexpr u64 Q = 431166034846567ULL;
static constexpr u64 P_INVERSE_MOD_Q = 52449289519716ULL;
static constexpr u64 SCAN_MAX = 37862796ULL;
static constexpr u64 EPSILON_LO_SCALED = 2439259423933906ULL;
static constexpr u64 EPSILON_HI_SCALED = 2439259423933907ULL;
static constexpr u64 INV_M_LO_SCALED = 258180334ULL;
static constexpr u64 INV_M_HI_SCALED = 258180335ULL;
static constexpr unsigned SCALE_BITS = 100;

std::string decimal(u128 value) {
    if (value == 0) return "0";
    std::string result;
    while (value != 0) {
        result.push_back(static_cast<char>('0' + value % 10));
        value /= 10;
    }
    return std::string(result.rbegin(), result.rend());
}

int main() {
    const u128 scale = u128(1) << SCALE_BITS;
    u64 accepted = 0;
    u64 rejected = 0;
    u64 undecided = 0;

    for (u64 distance = 1; distance <= SCAN_MAX; ++distance) {
        const u64 residue = static_cast<u64>((u128(distance) * P_INVERSE_MOD_Q) % Q);
        const u64 t = residue == 0 ? 0 : Q - residue;
        const u128 a_lower = u128(distance) * scale + u128(t) * EPSILON_LO_SCALED;
        const u128 a_upper = u128(distance) * scale + u128(t) * EPSILON_HI_SCALED;
        const u128 rhs_lower = u128(Q) * t * INV_M_LO_SCALED;
        const u128 rhs_upper = u128(Q) * t * INV_M_HI_SCALED;
        if (a_upper < rhs_lower) {
            ++accepted;
        } else if (a_lower >= rhs_upper) {
            ++rejected;
        } else {
            ++undecided;
        }
    }

    std::cout << "{\n"
              << "  \"P\": \"" << P << "\",\n"
              << "  \"Q\": \"" << Q << "\",\n"
              << "  \"accepted\": " << accepted << ",\n"
              << "  \"epsilon_hi_scaled\": \"" << EPSILON_HI_SCALED << "\",\n"
              << "  \"epsilon_lo_scaled\": \"" << EPSILON_LO_SCALED << "\",\n"
              << "  \"inv_m_hi_scaled\": \"" << INV_M_HI_SCALED << "\",\n"
              << "  \"inv_m_lo_scaled\": \"" << INV_M_LO_SCALED << "\",\n"
              << "  \"rejected\": " << rejected << ",\n"
              << "  \"result\": \"" << (undecided == 0 ? "CERTIFIED" : "UNDECIDED") << "\",\n"
              << "  \"scale_bits\": " << SCALE_BITS << ",\n"
              << "  \"scan_max\": " << SCAN_MAX << ",\n"
              << "  \"undecided\": " << undecided << "\n"
              << "}\n";
    return undecided == 0 && accepted == 18931398ULL ? 0 : 1;
}
