use crate::bigint::{ceil_div, floor_div, modulo_power_two, mul, pow2, sub};
use rug::Integer;

#[derive(Clone)]
pub struct Progression {
    pub lower: Integer,
    pub upper: Integer,
    pub residue: Integer,
    pub bits: u32,
}

impl Progression {
    pub fn normalize(&mut self) -> Result<bool, String> {
        if self.lower > self.upper {
            return Ok(false);
        }
        self.residue = modulo_power_two(&self.residue, self.bits);
        let modulus = pow2(self.bits);
        let mut first = sub(&self.lower, &self.residue);
        first = ceil_div(&first, &modulus)?;
        first *= &modulus;
        first += &self.residue;
        if first > self.upper {
            return Ok(false);
        }
        let mut last = sub(&self.upper, &self.residue);
        last = floor_div(&last, &modulus)?;
        last *= &modulus;
        last += &self.residue;
        self.lower = first;
        self.upper = last;
        if modulo_power_two(&sub(&self.lower, &self.residue), self.bits) != 0
            || modulo_power_two(&sub(&self.upper, &self.residue), self.bits) != 0
        {
            return Err("progression endpoint invariant failed".into());
        }
        Ok(true)
    }

    pub fn intersect_interval(
        &mut self,
        lower: Option<&Integer>,
        upper: Option<&Integer>,
    ) -> Result<bool, String> {
        if let Some(value) = lower
            && value > &self.lower
        {
            self.lower.clone_from(value);
        }
        if let Some(value) = upper
            && value < &self.upper
        {
            self.upper.clone_from(value);
        }
        self.normalize()
    }

    pub fn intersect_congruence(
        &mut self,
        coefficient: &Integer,
        rhs: &Integer,
        new_bits: u32,
    ) -> Result<bool, String> {
        if new_bits <= self.bits {
            let difference = sub(&mul(coefficient, &self.residue), rhs);
            return Ok(modulo_power_two(&difference, new_bits) == 0);
        }
        let difference = modulo_power_two(&sub(rhs, &mul(coefficient, &self.residue)), new_bits);
        if modulo_power_two(&difference, self.bits) != 0 {
            return Ok(false);
        }
        let extra = new_bits - self.bits;
        let reduced_rhs = difference >> self.bits;
        let reduced_coefficient = modulo_power_two(coefficient, extra);
        let modulus = pow2(extra);
        let inverse = reduced_coefficient
            .invert(&modulus)
            .map_err(|_| "noninvertible congruence coefficient".to_string())?;
        let lift = modulo_power_two(&(reduced_rhs * inverse), extra);
        self.residue += lift << self.bits;
        self.bits = new_bits;
        self.normalize()
    }

    pub fn count_capped(&self, cap: u64) -> Result<u64, String> {
        let count = self.count();
        if count > cap {
            Ok(cap + 1)
        } else {
            count
                .to_u64()
                .ok_or_else(|| "progression count does not fit u64".into())
        }
    }

    pub fn count(&self) -> Integer {
        let mut count = sub(&self.upper, &self.lower);
        count /= pow2(self.bits);
        count += 1;
        count
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn values(progression: &Progression) -> Vec<i32> {
        (-20..=20)
            .filter(|value| {
                let integer = Integer::from(*value);
                integer >= progression.lower
                    && integer <= progression.upper
                    && modulo_power_two(&sub(&integer, &progression.residue), progression.bits) == 0
            })
            .collect()
    }

    #[test]
    fn normalization_matches_brute_force() {
        for lower in -8..=8 {
            for upper in lower..=10 {
                for residue in -8..=8 {
                    for bits in 0..=4 {
                        let original = Progression {
                            lower: lower.into(),
                            upper: upper.into(),
                            residue: residue.into(),
                            bits,
                        };
                        let expected = values(&original);
                        let mut normalized = original;
                        let nonempty = normalized.normalize().unwrap();
                        assert_eq!(nonempty, !expected.is_empty());
                        if nonempty {
                            assert_eq!(values(&normalized), expected);
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn congruence_intersection_matches_brute_force() {
        for coefficient in [-7, -3, 1, 5, 9] {
            for rhs in -8..=8 {
                let mut progression = Progression {
                    lower: (-20).into(),
                    upper: 20.into(),
                    residue: 1.into(),
                    bits: 1,
                };
                let original = values(&progression);
                let nonempty = progression
                    .intersect_congruence(&coefficient.into(), &rhs.into(), 5)
                    .unwrap();
                let expected: Vec<i32> = original
                    .into_iter()
                    .filter(|value| {
                        modulo_power_two(
                            &sub(
                                &mul(&coefficient.into(), &Integer::from(*value)),
                                &rhs.into(),
                            ),
                            5,
                        ) == 0
                    })
                    .collect();
                assert_eq!(nonempty, !expected.is_empty());
                if nonempty {
                    assert_eq!(values(&progression), expected);
                }
            }
        }
    }

    #[test]
    fn interval_intersection_matches_brute_force() {
        for cut_lower in -22..=22 {
            for cut_upper in cut_lower..=22 {
                let mut progression = Progression {
                    lower: (-20).into(),
                    upper: 20.into(),
                    residue: 3.into(),
                    bits: 3,
                };
                let expected: Vec<i32> = values(&progression)
                    .into_iter()
                    .filter(|value| *value >= cut_lower && *value <= cut_upper)
                    .collect();
                let nonempty = progression
                    .intersect_interval(Some(&cut_lower.into()), Some(&cut_upper.into()))
                    .unwrap();
                assert_eq!(nonempty, !expected.is_empty());
                if nonempty {
                    assert_eq!(values(&progression), expected);
                }
            }
        }
    }

    #[test]
    fn empty_singleton_and_capped_counts() {
        let mut empty = Progression {
            lower: 2.into(),
            upper: 1.into(),
            residue: 1.into(),
            bits: 1,
        };
        assert!(!empty.normalize().unwrap());
        let mut singleton = Progression {
            lower: 3.into(),
            upper: 3.into(),
            residue: 1.into(),
            bits: 1,
        };
        assert!(singleton.normalize().unwrap());
        assert_eq!(singleton.count(), 1);
        assert_eq!(singleton.count_capped(1).unwrap(), 1);
        let large = Progression {
            lower: 1.into(),
            upper: 1_000_001.into(),
            residue: 1.into(),
            bits: 1,
        };
        assert_eq!(large.count_capped(256).unwrap(), 257);
    }
}
