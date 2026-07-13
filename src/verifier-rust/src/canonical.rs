use serde_json::Value;
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

pub fn canonical_text(value: &Value) -> Result<String, String> {
    serde_json::to_string(value).map_err(|error| error.to_string())
}

pub fn read(path: &Path) -> Result<Value, String> {
    let metadata = fs::symlink_metadata(path).map_err(|error| error.to_string())?;
    if !metadata.is_file() || metadata.file_type().is_symlink() {
        return Err(format!("input is not a regular file: {}", path.display()));
    }
    let raw = fs::read(path).map_err(|error| error.to_string())?;
    let value: Value = serde_json::from_slice(&raw).map_err(|error| error.to_string())?;
    let expected = format!("{}\n", canonical_text(&value)?).into_bytes();
    if raw != expected {
        return Err(format!("input JSON is not canonical: {}", path.display()));
    }
    Ok(value)
}

pub fn sha256_bytes(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    digest.iter().map(|byte| format!("{byte:02x}")).collect()
}

pub fn sha256_file(path: &Path) -> Result<String, String> {
    fs::read(path)
        .map(|bytes| sha256_bytes(&bytes))
        .map_err(|error| error.to_string())
}

pub fn object_id(domain: &str, value: &Value) -> Result<String, String> {
    let mut bytes = domain.as_bytes().to_vec();
    bytes.push(0);
    bytes.extend(canonical_text(value)?.as_bytes());
    Ok(sha256_bytes(&bytes))
}

pub fn atomic_write(path: &Path, value: &Value) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "output has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let temporary = path.with_extension(format!("tmp.{}", std::process::id()));
    fs::write(&temporary, format!("{}\n", canonical_text(value)?))
        .map_err(|error| error.to_string())?;
    fs::rename(&temporary, path).map_err(|error| error.to_string())
}

pub fn executable_sha256() -> Result<String, String> {
    let executable = std::env::current_exe().map_err(|error| error.to_string())?;
    sha256_file(&executable)
}
