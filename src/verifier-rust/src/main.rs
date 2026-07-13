#![forbid(unsafe_code)]

mod bigint;
mod canonical;
mod config;
mod progression;
mod search;

use canonical::{atomic_write, executable_sha256, object_id, read, sha256_file};
use config::{parse_config, parse_unit};
use search::replay;
use serde_json::{Map, Value, json};
use std::collections::BTreeMap;
use std::env;
use std::path::PathBuf;

const SOURCE_SHA256: &str = env!("COLLATZ_RUST_SOURCE_SHA256");

struct Arguments {
    config: PathBuf,
    unit: PathBuf,
    output: PathBuf,
    math_certificate: PathBuf,
    enum_threshold: u64,
    debug_terminal_dump: Option<PathBuf>,
}

fn arguments() -> Result<Arguments, String> {
    let mut values = env::args().skip(1);
    let mut config = None;
    let mut unit = None;
    let mut output = None;
    let mut math_certificate = PathBuf::from("certificates/analytic/m92_96_reductions.json");
    let mut enum_threshold = 256;
    let mut debug_terminal_dump = None;
    while let Some(option) = values.next() {
        let value = values
            .next()
            .ok_or_else(|| format!("missing value for {option}"))?;
        match option.as_str() {
            "--config" => config = Some(value.into()),
            "--unit" => unit = Some(value.into()),
            "--output" => output = Some(value.into()),
            "--math-certificate" => math_certificate = value.into(),
            "--enum-threshold" => {
                enum_threshold = value
                    .parse()
                    .map_err(|_| "invalid enum threshold".to_string())?
            }
            "--debug-terminal-dump" => debug_terminal_dump = Some(value.into()),
            _ => return Err(format!("unknown option: {option}")),
        }
    }
    Ok(Arguments {
        config: config.ok_or_else(|| "--config is required".to_string())?,
        unit: unit.ok_or_else(|| "--unit is required".to_string())?,
        output: output.ok_or_else(|| "--output is required".to_string())?,
        math_certificate,
        enum_threshold,
        debug_terminal_dump,
    })
}

fn counter_map(output: &search::SearchOutput) -> Map<String, Value> {
    let mut values = BTreeMap::from([
        (
            "bound_prunes".to_string(),
            output.counters.bound_prunes.to_string(),
        ),
        (
            "deterministic_nodes".to_string(),
            output.counters.deterministic_nodes.to_string(),
        ),
        (
            "deterministic_values".to_string(),
            output.counters.deterministic_values.to_string(),
        ),
        (
            "final_intervals".to_string(),
            output.counters.final_intervals.to_string(),
        ),
        (
            "prefix_prunes".to_string(),
            output.counters.prefix_prunes.to_string(),
        ),
        (
            "recursive_nodes".to_string(),
            output.counters.recursive_nodes.to_string(),
        ),
        (
            "represented_input_count".to_string(),
            output.represented_input_count.to_string(),
        ),
    ]);
    for index in 1..output.counters.level_nodes.len() {
        values.insert(
            format!("level_{index}"),
            output.counters.level_nodes[index].to_string(),
        );
    }
    values
        .into_iter()
        .map(|(key, value)| (key, Value::String(value)))
        .collect()
}

fn run() -> Result<i32, String> {
    let args = arguments()?;
    let math_hash = sha256_file(&args.math_certificate)?;
    let math_json = read(&args.math_certificate)?;
    let config_json = read(&args.config)?;
    let config = parse_config(&config_json, &math_hash, &math_json)?;
    let unit_json = read(&args.unit)?;
    let unit = parse_unit(&unit_json, &config)?;
    let search = replay(
        &config,
        &unit,
        args.enum_threshold,
        args.debug_terminal_dump.is_some(),
    )?;
    if let Some(path) = &args.debug_terminal_dump {
        let count = search
            .represented_input_count
            .to_u64()
            .ok_or_else(|| "debug terminal count does not fit u64".to_string())?;
        if count > 10_000
            || count > args.enum_threshold
            || search.terminal_decisions.len() as u64 != count
        {
            return Err(
                "debug terminal dump requires at most min(enum-threshold,10000) values".into(),
            );
        }
        let decisions: Vec<Value> = search
            .terminal_decisions
            .iter()
            .map(|(a1, outcome)| json!({"a1": a1, "outcome": outcome}))
            .collect();
        atomic_write(
            path,
            &json!({
                "decisions": decisions,
                "schema": "collatz.terminal-dump.v1",
                "unit_id": unit.unit_id,
            }),
        )?;
    }
    let mut result = json!({
        "binary_sha256": executable_sha256()?,
        "config_id": config.config_id,
        "counters": Value::Object(counter_map(&search)),
        "engine": "independent-rust-verifier",
        "hits": search.counters.hits.to_string(),
        "math_certificate_sha256": config.math_certificate_sha256,
        "max_integer_bits": search.counters.max_integer_bits.to_string(),
        "outcome": if search.counters.hits == 0 { "NO_SURVIVOR" } else { "SURVIVOR" },
        "schema": "collatz.engine-result.v1",
        "semantic_parameters": {"enum_threshold": args.enum_threshold.to_string()},
        "source_sha256": SOURCE_SHA256,
        "unit_id": unit.unit_id,
    });
    let identifier = object_id("collatz.engine-result.v1", &result)?;
    result
        .as_object_mut()
        .unwrap()
        .insert("result_id".into(), Value::String(identifier));
    atomic_write(&args.output, &result)?;
    println!(
        "{}",
        serde_json::to_string(&result).map_err(|error| error.to_string())?
    );
    Ok(if search.counters.hits == 0 { 0 } else { 1 })
}

fn main() {
    match run() {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("ERROR: {error}");
            std::process::exit(2);
        }
    }
}
