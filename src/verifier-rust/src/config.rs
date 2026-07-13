use crate::bigint::parse_decimal;
use crate::canonical::object_id;
use rug::Integer;
use serde_json::{Map, Value};
use std::collections::BTreeSet;

#[derive(Clone)]
pub struct CaseConfig {
    pub m: u32,
    pub x: Integer,
    pub window_num: Integer,
    pub window_den: Integer,
    pub depth: usize,
    pub k1_min: u32,
    pub k1_max: u32,
    pub k_caps: Vec<u32>,
    pub stage_minima: Vec<Integer>,
    pub alpha_lower_num: Integer,
    pub alpha_lower_den: Integer,
    pub alpha_upper_num: Integer,
    pub alpha_upper_den: Integer,
    pub first_positive_surplus: u64,
    pub math_certificate_sha256: String,
    pub config_id: String,
}

#[derive(Clone)]
pub struct WorkUnit {
    pub unit_id: String,
    pub config_id: String,
    pub m: u32,
    pub k1: u32,
    pub root_first: Integer,
    pub root_last: Integer,
    pub root_count: Integer,
    pub index_start: Integer,
    pub index_end: Integer,
}

fn object<'a>(value: &'a Value, label: &str) -> Result<&'a Map<String, Value>, String> {
    value
        .as_object()
        .ok_or_else(|| format!("{label} is not an object"))
}

fn exact_keys(object: &Map<String, Value>, expected: &[&str], label: &str) -> Result<(), String> {
    let actual: BTreeSet<&str> = object.keys().map(String::as_str).collect();
    let wanted: BTreeSet<&str> = expected.iter().copied().collect();
    if actual != wanted {
        return Err(format!("{label} keys mismatch"));
    }
    Ok(())
}

fn text<'a>(object: &'a Map<String, Value>, key: &str) -> Result<&'a str, String> {
    object
        .get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("missing string {key}"))
}

fn hash(object: &Map<String, Value>, key: &str) -> Result<String, String> {
    let value = text(object, key)?;
    if value.len() != 64
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit() && !byte.is_ascii_uppercase())
    {
        return Err(format!("invalid SHA-256 {key}"));
    }
    Ok(value.to_string())
}

fn integer(object: &Map<String, Value>, key: &str, positive: bool) -> Result<Integer, String> {
    parse_decimal(text(object, key)?, positive, key)
}

fn small(object: &Map<String, Value>, key: &str, positive: bool) -> Result<u64, String> {
    let value = text(object, key)?;
    parse_decimal(value, positive, key)?;
    value
        .parse::<u64>()
        .map_err(|_| format!("{key} does not fit u64"))
}

pub fn parse_config(
    value: &Value,
    math_hash: &str,
    math_certificate: &Value,
) -> Result<CaseConfig, String> {
    let root = object(value, "config")?;
    exact_keys(
        root,
        &[
            "X",
            "alpha_bracket",
            "depth",
            "first_positive_surplus",
            "k1_range",
            "k_caps",
            "m",
            "math_certificate_sha256",
            "schema",
            "stage_minima",
            "window",
        ],
        "config",
    )?;
    if text(root, "schema")? != "collatz.case-config.v1" {
        return Err("config schema mismatch".into());
    }
    let m = small(root, "m", true)? as u32;
    if !(92..=96).contains(&m) {
        return Err("unsupported case".into());
    }
    let depth = small(root, "depth", true)? as usize;
    let certificate_hash = hash(root, "math_certificate_sha256")?;
    if certificate_hash != math_hash {
        return Err("math certificate hash mismatch".into());
    }
    let math = object(math_certificate, "mathematical certificate")?;
    if text(math, "schema")? != "collatz.mathematical-reductions.v1" {
        return Err("mathematical certificate schema mismatch".into());
    }
    let records = math
        .get("case_certificates")
        .and_then(Value::as_array)
        .ok_or_else(|| "mathematical case records missing".to_string())?;
    let expected = records
        .iter()
        .find(|record| {
            record
                .get("case")
                .and_then(Value::as_str)
                .is_some_and(|case| case == m.to_string())
        })
        .and_then(|record| record.get("search_config"))
        .ok_or_else(|| "mathematical search config missing".to_string())?;
    let mut actual = value.clone();
    actual
        .as_object_mut()
        .unwrap()
        .remove("math_certificate_sha256");
    if &actual != expected {
        return Err("config semantics do not match mathematical certificate".into());
    }
    let window = object(root.get("window").unwrap(), "window")?;
    exact_keys(window, &["denominator", "numerator"], "window")?;
    let range = object(root.get("k1_range").unwrap(), "k1 range")?;
    exact_keys(range, &["max", "min"], "k1 range")?;
    let alpha = object(root.get("alpha_bracket").unwrap(), "alpha bracket")?;
    exact_keys(
        alpha,
        &["lower_den", "lower_num", "upper_den", "upper_num"],
        "alpha bracket",
    )?;
    let caps = root
        .get("k_caps")
        .and_then(Value::as_array)
        .ok_or_else(|| "k_caps is not an array".to_string())?;
    let minima = root
        .get("stage_minima")
        .and_then(Value::as_array)
        .ok_or_else(|| "stage_minima is not an array".to_string())?;
    if caps.len() != depth || minima.len() != depth + 1 {
        return Err("config array dimensions mismatch".into());
    }
    let mut k_caps = Vec::with_capacity(caps.len());
    for item in caps {
        let holder = Map::from_iter([("value".into(), item.clone())]);
        k_caps.push(small(&holder, "value", true)? as u32);
    }
    let mut stage_minima = Vec::with_capacity(minima.len());
    for item in minima {
        let holder = Map::from_iter([("value".into(), item.clone())]);
        stage_minima.push(integer(&holder, "value", true)?);
    }
    Ok(CaseConfig {
        m,
        x: integer(root, "X", true)?,
        window_num: integer(window, "numerator", true)?,
        window_den: integer(window, "denominator", true)?,
        depth,
        k1_min: small(range, "min", true)? as u32,
        k1_max: small(range, "max", true)? as u32,
        k_caps,
        stage_minima,
        alpha_lower_num: integer(alpha, "lower_num", true)?,
        alpha_lower_den: integer(alpha, "lower_den", true)?,
        alpha_upper_num: integer(alpha, "upper_num", true)?,
        alpha_upper_den: integer(alpha, "upper_den", true)?,
        first_positive_surplus: small(root, "first_positive_surplus", true)?,
        math_certificate_sha256: certificate_hash,
        config_id: object_id("collatz.case-config.v1", value)?,
    })
}

pub fn parse_unit(value: &Value, config: &CaseConfig) -> Result<WorkUnit, String> {
    let root = object(value, "unit")?;
    exact_keys(
        root,
        &[
            "config_id",
            "index_range",
            "k1",
            "m",
            "root",
            "schema",
            "unit_id",
        ],
        "unit",
    )?;
    if text(root, "schema")? != "collatz.work-unit.v1" {
        return Err("unit schema mismatch".into());
    }
    let claimed_id = hash(root, "unit_id")?;
    let mut identity = value.clone();
    identity.as_object_mut().unwrap().remove("unit_id");
    if claimed_id != object_id("collatz.work-unit.v1", &identity)? {
        return Err("unit ID mismatch".into());
    }
    let config_id = hash(root, "config_id")?;
    let m = small(root, "m", true)? as u32;
    let k1 = small(root, "k1", true)? as u32;
    if config_id != config.config_id || m != config.m || k1 < config.k1_min || k1 > config.k1_max {
        return Err("unit/config mismatch".into());
    }
    let progression = object(root.get("root").unwrap(), "root")?;
    exact_keys(
        progression,
        &["bits", "count", "first", "last", "residue"],
        "root",
    )?;
    if text(progression, "bits")? != "1" || text(progression, "residue")? != "1" {
        return Err("root is not an odd progression".into());
    }
    let range = object(root.get("index_range").unwrap(), "index range")?;
    exact_keys(range, &["end", "start"], "index range")?;
    Ok(WorkUnit {
        unit_id: claimed_id,
        config_id,
        m,
        k1,
        root_first: integer(progression, "first", false)?,
        root_last: integer(progression, "last", false)?,
        root_count: integer(progression, "count", false)?,
        index_start: integer(range, "start", false)?,
        index_end: integer(range, "end", false)?,
    })
}
