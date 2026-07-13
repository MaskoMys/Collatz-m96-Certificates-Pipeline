use rug::{Complete, Integer};

pub fn pow2(bits: u32) -> Integer {
    Integer::from(1) << bits
}

pub fn floor_div(numerator: &Integer, denominator: &Integer) -> Result<Integer, String> {
    if denominator <= &0 {
        return Err("floor_div denominator is not positive".into());
    }
    Ok(numerator.clone().div_rem_floor(denominator.clone()).0)
}

pub fn ceil_div(numerator: &Integer, denominator: &Integer) -> Result<Integer, String> {
    if denominator <= &0 {
        return Err("ceil_div denominator is not positive".into());
    }
    Ok(numerator.clone().div_rem_ceil(denominator.clone()).0)
}

pub fn modulo_power_two(value: &Integer, bits: u32) -> Integer {
    let modulus = pow2(bits);
    value.clone().div_rem_floor(modulus).1
}

pub fn valuation_two(value: &Integer) -> Result<u32, String> {
    if value == &0 {
        return Err("v2(0) is undefined".into());
    }
    value
        .find_one(0)
        .ok_or_else(|| "cannot find a set bit".to_string())
}

pub fn floor_log2(value: &Integer) -> Result<u32, String> {
    if value <= &0 {
        return Err("floor_log2 argument is not positive".into());
    }
    Ok(value.significant_bits() - 1)
}

pub fn add(left: &Integer, right: &Integer) -> Integer {
    (left + right).complete()
}

pub fn sub(left: &Integer, right: &Integer) -> Integer {
    (left - right).complete()
}

pub fn mul(left: &Integer, right: &Integer) -> Integer {
    (left * right).complete()
}

pub fn shl(value: &Integer, bits: u32) -> Integer {
    (value << bits).complete()
}

pub fn shr(value: &Integer, bits: u32) -> Integer {
    (value >> bits).complete()
}

pub fn max3(first: &Integer, second: &Integer, third: &Integer) -> Integer {
    std::cmp::max(first, std::cmp::max(second, third)).clone()
}

pub fn parse_decimal(value: &str, positive: bool, label: &str) -> Result<Integer, String> {
    if value.is_empty()
        || (value.len() > 1 && value.starts_with('0'))
        || !value.bytes().all(|byte| byte.is_ascii_digit())
        || (positive && value == "0")
    {
        return Err(format!("{label} is not a canonical decimal string"));
    }
    Integer::from_str_radix(value, 10).map_err(|_| format!("cannot parse {label}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signed_floor_and_ceiling() {
        for numerator in -9..=9 {
            for denominator in 1..=5 {
                let n = Integer::from(numerator);
                let d = Integer::from(denominator);
                let floor = floor_div(&n, &d).unwrap();
                let ceil = ceil_div(&n, &d).unwrap();
                assert!(mul(&floor, &d) <= n);
                assert!(mul(&add(&floor, &1.into()), &d) > n);
                assert!(mul(&ceil, &d) >= n);
                assert!(mul(&sub(&ceil, &1.into()), &d) < n);
            }
        }
    }

    #[test]
    fn powers_valuations_and_logs_cover_boundaries() {
        assert!(valuation_two(&0.into()).is_err());
        assert!(floor_log2(&0.into()).is_err());
        for bits in 0..=127 {
            let power = pow2(bits);
            assert_eq!(valuation_two(&power).unwrap(), bits);
            assert_eq!(valuation_two(&(-power.clone())).unwrap(), bits);
            assert_eq!(floor_log2(&power).unwrap(), bits);
            assert_eq!(modulo_power_two(&(-1).into(), bits), pow2(bits) - 1);
        }
    }
}
