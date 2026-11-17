use serde_json::{json, Value};
use std::io::{self, Read};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut bytes = Vec::new();
    io::stdin()
        .take(8 * 1024 * 1024 + 1)
        .read_to_end(&mut bytes)?;
    if bytes.len() > 8 * 1024 * 1024 {
        return Err("request-limit".into());
    }
    let request: Value = serde_json::from_slice(&bytes)?;
    if request["protocol"] != "lekalo/runtime/v1"
        || !request["request_id"]
            .as_str()
            .is_some_and(|id| id.len() == 71 && id.starts_with("sha256:"))
    {
        return Err("request-envelope".into());
    }
    let result = dispatch(
        request["operation"].as_str().ok_or("operation")?,
        &request["input"],
    )?;
    print!(
        "{}",
        json!({"protocol":"lekalo/runtime/v1","request_id":request["request_id"],"result":result})
    );
    Ok(())
}

fn dispatch(op: &str, input: &Value) -> Result<Value, Box<dyn std::error::Error>> {
    if op == "describe" {
        return Ok(
            json!({"id":"lekalo-hlv","version":"0.1.0","rules_api":[],"capabilities":["trace.mappings/v1"],"operations":["trace.mappings"]}),
        );
    }
    if op != "trace.mappings" || input["schema"] != "lekalo/trace-mappings/v1" {
        return Err("operation-input".into());
    }
    let rows = input["mappings"].as_array().ok_or("mappings")?;
    if rows.len() > 8192 {
        return Err("mapping-limit".into());
    }
    let mut results = Vec::new();
    for row in rows {
        let required = row["required"]
            .as_array()
            .ok_or("required")?
            .iter()
            .any(|v| v == "hlv");
        let revision = row["revision"].as_str().ok_or("revision")?;
        let aliases = row["aliases"].as_array().ok_or("aliases")?;
        let state = if !required {
            "not-applicable"
        } else {
            match lekalo_hlv::assess_mapping(
                aliases
                    .iter()
                    .filter(|v| v["system"] == "hlv")
                    .map(|v| v["revision"].as_str()),
                revision,
            ) {
                Ok(()) => "valid",
                Err(lekalo_hlv::MappingFailure::Missing) => "missing",
                Err(lekalo_hlv::MappingFailure::Conflicting) => "conflicting",
                Err(lekalo_hlv::MappingFailure::Stale) => "stale",
            }
        };
        results.push(json!({"id":row["id"],"state":state}));
    }
    Ok(json!({"schema":"lekalo/trace-mappings/v1","results":results}))
}
