use crate::bigint::{
    add, ceil_div, floor_div, floor_log2, max3, modulo_power_two, mul, pow2, shl, shr, sub,
    valuation_two,
};
use crate::config::{CaseConfig, WorkUnit};
use crate::progression::Progression;
use rug::Integer;

#[derive(Default)]
pub struct Counters {
    pub recursive_nodes: u64,
    pub final_intervals: u64,
    pub hits: u64,
    pub prefix_prunes: u64,
    pub deterministic_values: u64,
    pub deterministic_nodes: u64,
    pub bound_prunes: u64,
    pub max_integer_bits: u64,
    pub level_nodes: Vec<u64>,
}

pub struct SearchOutput {
    pub counters: Counters,
    pub represented_input_count: Integer,
    pub terminal_decisions: Vec<(String, String)>,
}

struct Replay<'a> {
    config: &'a CaseConfig,
    enum_threshold: u64,
    counters: Counters,
    powers_three: Vec<Integer>,
    debug_terminal_dump: bool,
    terminal_decisions: Vec<(String, String)>,
}

fn increment(value: &mut u64, label: &str) -> Result<(), String> {
    *value = value
        .checked_add(1)
        .ok_or_else(|| format!("{label} overflow"))?;
    Ok(())
}

fn sum(left: u64, right: u64, label: &str) -> Result<u64, String> {
    left.checked_add(right)
        .ok_or_else(|| format!("{label} overflow"))
}

impl<'a> Replay<'a> {
    fn power_three(&mut self, exponent: u32) -> Integer {
        while self.powers_three.len() <= exponent as usize {
            let mut next = self.powers_three.last().unwrap().clone();
            next *= 3;
            self.powers_three.push(next);
        }
        self.powers_three[exponent as usize].clone()
    }

    fn observe(&mut self, value: &Integer) {
        self.counters.max_integer_bits = self
            .counters
            .max_integer_bits
            .max(value.significant_bits() as u64);
    }

    fn floor_alpha(&self, value: u64) -> Result<u64, String> {
        let n = Integer::from(value);
        let lower = floor_div(
            &mul(&self.config.alpha_lower_num, &n),
            &self.config.alpha_lower_den,
        )?;
        let upper = floor_div(
            &mul(&self.config.alpha_upper_num, &n),
            &self.config.alpha_upper_den,
        )?;
        if lower != upper {
            return Err("alpha bracket leaves an undecided floor".into());
        }
        lower
            .to_u64()
            .ok_or_else(|| "floor alpha does not fit u64".into())
    }

    fn assert_state(
        &self,
        live: &Progression,
        p: &Integer,
        q: &Integer,
        shift: u32,
    ) -> Result<(), String> {
        if live.lower > live.upper || modulo_power_two(&live.residue, live.bits) != live.residue {
            return Err("invalid progression state".into());
        }
        if p.is_even() {
            return Err("affine coefficient is even".into());
        }
        if modulo_power_two(&add(&mul(p, &live.residue), q), shift) != 0 {
            return Err("affine divisibility invariant failed".into());
        }
        let represented = shr(&add(&mul(p, &live.residue), q), shift);
        if represented.is_even() {
            return Err("represented local minimum is even".into());
        }
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    fn deterministic_finish(
        &mut self,
        level: usize,
        k1: u32,
        k: u32,
        k_sum: u64,
        l_sum: u64,
        p: &Integer,
        q: &Integer,
        shift: u32,
        live: &Progression,
    ) -> Result<(), String> {
        let step = pow2(live.bits);
        let mut a = live.lower.clone();
        let mut visited = Integer::from(0);
        while a <= live.upper {
            visited += 1;
            increment(
                &mut self.counters.deterministic_values,
                "deterministic value count",
            )?;
            let numerator = add(&mul(p, &a), q);
            if modulo_power_two(&numerator, shift) != 0 {
                return Err("nonintegral deterministic affine state".into());
            }
            let mut ai = shr(&numerator, shift);
            if ai.is_even() {
                return Err("even deterministic state".into());
            }
            let mut current_k = k;
            let mut current_k_sum = k_sum;
            let mut current_l_sum = l_sum;
            let n1 = sub(&shl(&a, k1), &Integer::from(1));
            let mut terminal_reason = None;
            for index in level..=self.config.depth {
                increment(
                    &mut self.counters.deterministic_nodes,
                    "deterministic node count",
                )?;
                let three = self.power_three(current_k);
                let value = sub(&mul(&ai, &three), &Integer::from(1));
                let ell = valuation_two(&value)?;
                let next_n = shr(&value, ell);
                let required = max3(&self.config.stage_minima[index], &self.config.x, &n1);
                if next_n < required {
                    terminal_reason = Some("STAGE_MINIMUM");
                    break;
                }
                let next_l_sum = sum(current_l_sum, ell as u64, "L sum")?;
                if current_k_sum >= self.config.first_positive_surplus {
                    return Err("prefix beyond certified A28 gate".into());
                }
                if sum(current_k_sum, next_l_sum, "prefix sum")?
                    > self.floor_alpha(current_k_sum)?
                {
                    increment(&mut self.counters.prefix_prunes, "prefix prune count")?;
                    terminal_reason = Some("PREFIX_GATE");
                    break;
                }
                if index == self.config.depth {
                    increment(&mut self.counters.hits, "hit count")?;
                    terminal_reason = Some("SURVIVOR");
                    break;
                }
                let next_k = valuation_two(&add(&next_n, &Integer::from(1)))?;
                if next_k == 0 || next_k > self.config.k_caps[index] {
                    terminal_reason = Some("CAP");
                    break;
                }
                ai = shr(&add(&next_n, &Integer::from(1)), next_k);
                if ai.is_even() {
                    return Err("next a is even".into());
                }
                current_k = next_k;
                current_k_sum = sum(current_k_sum, next_k as u64, "K sum")?;
                current_l_sum = next_l_sum;
            }
            let reason = terminal_reason
                .ok_or_else(|| "deterministic value has no terminal reason".to_string())?;
            if self.debug_terminal_dump {
                self.terminal_decisions
                    .push((a.to_string(), reason.to_string()));
            }
            a += &step;
        }
        if visited != live.count() {
            return Err("deterministic iteration did not cover progression".into());
        }
        Ok(())
    }

    #[allow(clippy::too_many_arguments)]
    fn recurse(
        &mut self,
        level: usize,
        k1: u32,
        k: u32,
        k_sum: u64,
        l_sum: u64,
        p: &Integer,
        q: &Integer,
        shift: u32,
        live: &Progression,
    ) -> Result<(), String> {
        self.assert_state(live, p, q, shift)?;
        increment(&mut self.counters.recursive_nodes, "recursive node count")?;
        self.observe(&live.lower);
        self.observe(&live.upper);
        self.observe(p);
        self.observe(q);
        if live.count_capped(self.enum_threshold)? <= self.enum_threshold {
            return self.deterministic_finish(level, k1, k, k_sum, l_sum, p, q, shift, live);
        }

        let two_k = pow2(k);
        let two_shift = pow2(shift);
        let affine_upper = add(&mul(p, &live.upper), q);
        let n_max = shr(&sub(&mul(&two_k, &affine_upper), &two_shift), shift);
        let n1_min = sub(&shl(&live.lower, k1), &Integer::from(1));
        let extra = self.config.stage_minima[level].clone();
        let lower_bound = max3(&extra, &self.config.x, &n1_min);
        let power_k = self.power_three(k);
        let mut limit_numerator = sub(&mul(&power_k, &add(&n_max, &Integer::from(1))), &two_k);
        limit_numerator /= mul(&two_k, &lower_bound);
        if limit_numerator < 2 {
            increment(&mut self.counters.bound_prunes, "bound prune count")?;
            return Ok(());
        }
        let ell_max = floor_log2(&limit_numerator)?;
        for ell in 1..=ell_max {
            let next_l_sum = sum(l_sum, ell as u64, "L sum")?;
            if k_sum >= self.config.first_positive_surplus {
                return Err("prefix beyond certified A28 gate".into());
            }
            if sum(k_sum, next_l_sum, "prefix sum")? > self.floor_alpha(k_sum)? {
                increment(&mut self.counters.prefix_prunes, "prefix prune count")?;
                continue;
            }
            let mut branch = live.clone();
            let affine_denominator = mul(&power_k, p);
            let lower_numerator = sub(
                &add(&mul(&extra, &pow2(shift + ell)), &pow2(shift)),
                &mul(&power_k, q),
            );
            let lower = ceil_div(&lower_numerator, &affine_denominator)?;
            if !branch.intersect_interval(Some(&lower), None)? {
                continue;
            }
            let coefficient = sub(&mul(&power_k, p), &pow2(k1 + shift + ell));
            let constant = add(&sub(&mul(&power_k, q), &pow2(shift)), &pow2(shift + ell));
            let linear_ok = if coefficient > 0 {
                let lower = ceil_div(&(-constant.clone()), &coefficient)?;
                branch.intersect_interval(Some(&lower), None)?
            } else if coefficient < 0 {
                let upper = floor_div(&constant, &(-coefficient.clone()))?;
                branch.intersect_interval(None, Some(&upper))?
            } else {
                constant >= 0
            };
            if !linear_ok {
                continue;
            }
            let branch_affine_upper = add(&mul(p, &branch.upper), q);
            let branch_n_max = shr(
                &sub(&mul(&power_k, &branch_affine_upper), &pow2(shift)),
                shift + ell,
            );
            if level == self.config.depth {
                increment(&mut self.counters.final_intervals, "final interval count")?;
                let bits = shift + ell + 1;
                let rhs = sub(&add(&pow2(shift + ell), &pow2(shift)), &mul(&power_k, q));
                if branch.intersect_congruence(&mul(&power_k, p), &rhs, bits)? {
                    increment(&mut self.counters.hits, "hit count")?;
                }
                continue;
            }
            let k_max =
                floor_log2(&add(&branch_n_max, &Integer::from(1)))?.min(self.config.k_caps[level]);
            let p2 = mul(&power_k, p);
            let q_base = add(
                &mul(&power_k, q),
                &mul(&sub(&pow2(ell), &Integer::from(1)), &pow2(shift)),
            );
            let mut exponent = shift + ell + 1;
            let mut continuation = branch;
            if !continuation.intersect_congruence(&p2, &(-q_base.clone()), exponent)? {
                continue;
            }
            for next_k in 1..=k_max {
                if continuation.bits != exponent {
                    return Err("unexpected Hensel precision".into());
                }
                let representative = add(&mul(&p2, &continuation.residue), &q_base);
                let bit = representative.get_bit(exponent);
                let mut exact = continuation.clone();
                let mut next = continuation.clone();
                exact.bits = exponent + 1;
                next.bits = exponent + 1;
                if !bit {
                    exact.residue += pow2(exponent);
                } else {
                    next.residue += pow2(exponent);
                }
                let exact_ok = exact.normalize()?;
                let next_ok = next.normalize()?;
                let mut child_count = Integer::from(0);
                if exact_ok {
                    child_count += exact.count();
                }
                if next_ok {
                    child_count += next.count();
                }
                if child_count != continuation.count() {
                    return Err("Hensel children do not exactly cover parent".into());
                }
                if exact_ok {
                    let exact_value = add(&mul(&p2, &exact.residue), &q_base);
                    if modulo_power_two(&exact_value, exponent) != 0
                        || !exact_value.get_bit(exponent)
                    {
                        return Err("Hensel exact child has wrong valuation".into());
                    }
                }
                if next_ok
                    && modulo_power_two(&add(&mul(&p2, &next.residue), &q_base), exponent + 1) != 0
                {
                    return Err("Hensel continuation child is not divisible".into());
                }
                if exact_ok {
                    increment(&mut self.counters.level_nodes[level], "level node count")?;
                    self.recurse(
                        level + 1,
                        k1,
                        next_k,
                        sum(k_sum, next_k as u64, "K sum")?,
                        next_l_sum,
                        &p2,
                        &q_base,
                        exponent,
                        &exact,
                    )?;
                }
                if !next_ok {
                    break;
                }
                continuation = next;
                exponent += 1;
            }
        }
        Ok(())
    }
}

pub fn replay(
    config: &CaseConfig,
    unit: &WorkUnit,
    enum_threshold: u64,
    debug_terminal_dump: bool,
) -> Result<SearchOutput, String> {
    if enum_threshold == 0 {
        return Err("enum threshold must be positive".into());
    }
    if unit.config_id != config.config_id || unit.m != config.m {
        return Err("unit/config identity mismatch".into());
    }
    let mut n1_max = mul(&config.window_num, &config.x);
    n1_max /= &config.window_den;
    let divisor = pow2(unit.k1);
    let lower = ceil_div(&add(&config.x, &Integer::from(1)), &divisor)?;
    let mut upper = add(&n1_max, &Integer::from(1));
    upper /= &divisor;
    let first = if lower.is_even() {
        add(&lower, &Integer::from(1))
    } else {
        lower
    };
    let last = if upper.is_even() {
        sub(&upper, &Integer::from(1))
    } else {
        upper
    };
    let count = if first > last {
        Integer::from(0)
    } else {
        let mut value = sub(&last, &first);
        value /= 2;
        value += 1;
        value
    };
    let expected_last = if count == 0 {
        sub(&first, &Integer::from(2))
    } else {
        last
    };
    if unit.root_first != first || unit.root_last != expected_last || unit.root_count != count {
        return Err("unit root is not derived from config".into());
    }
    if count == 0 || unit.index_start > unit.index_end || unit.index_end >= count {
        return Err("invalid nonempty unit interval".into());
    }
    let mut represented_input_count = sub(&unit.index_end, &unit.index_start);
    represented_input_count += 1;
    let mut two_start = unit.index_start.clone();
    two_start *= 2;
    let mut two_end = unit.index_end.clone();
    two_end *= 2;
    let mut root = Progression {
        lower: add(&unit.root_first, &two_start),
        upper: add(&unit.root_first, &two_end),
        residue: 1.into(),
        bits: 1,
    };
    if !root.normalize()? {
        return Err("nonempty unit normalized to empty".into());
    }
    let mut replay = Replay {
        config,
        enum_threshold,
        counters: Counters {
            level_nodes: vec![0; config.depth + 1],
            ..Counters::default()
        },
        powers_three: vec![1.into()],
        debug_terminal_dump,
        terminal_decisions: Vec::new(),
    };
    replay.recurse(
        1,
        unit.k1,
        unit.k1,
        unit.k1 as u64,
        0,
        &Integer::from(1),
        &Integer::from(0),
        0,
        &root,
    )?;
    Ok(SearchOutput {
        counters: replay.counters,
        represented_input_count,
        terminal_decisions: replay.terminal_decisions,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn known_synthetic_survivor_is_reported() {
        let config = CaseConfig {
            m: 92,
            x: 1.into(),
            window_num: 1.into(),
            window_den: 1.into(),
            depth: 1,
            k1_min: 1,
            k1_max: 1,
            k_caps: vec![1],
            stage_minima: vec![1.into(), 1.into()],
            alpha_lower_num: 100.into(),
            alpha_lower_den: 1.into(),
            alpha_upper_num: 100.into(),
            alpha_upper_den: 1.into(),
            first_positive_surplus: 1000,
            math_certificate_sha256: "synthetic".into(),
            config_id: "synthetic".into(),
        };
        let unit = WorkUnit {
            unit_id: "synthetic".into(),
            config_id: "synthetic".into(),
            m: 92,
            k1: 1,
            root_first: 1.into(),
            root_last: 1.into(),
            root_count: 1.into(),
            index_start: 0.into(),
            index_end: 0.into(),
        };
        let result = replay(&config, &unit, 256, false).unwrap();
        assert_eq!(result.counters.hits, 1);
    }
}
