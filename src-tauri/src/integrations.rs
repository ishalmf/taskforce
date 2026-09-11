use crate::models::IntegrationStatus;
use crate::storage::copy_backup;
use serde_json::{json, Value};
use std::fs;
use std::path::{Path, PathBuf};

const OPENCODE_PLUGIN: &str = include_str!("../../integrations/opencode/taskforce.js");
const GEMINI_HOOK: &str = include_str!("../../integrations/gemini/taskforce-hook.cjs");
const MARKER: &str = "Taskforce integration";
const GEMINI_HOOK_NAME: &str = "taskforce-completion";

pub fn status() -> Result<IntegrationStatus, String> {
    Ok(IntegrationStatus {
        opencode: file_has_marker(&opencode_path()),
        gemini: gemini_is_installed()?,
    })
}

pub fn set(name: &str, enabled: bool) -> Result<IntegrationStatus, String> {
    match (name, enabled) {
        ("opencode", true) => install_opencode()?,
        ("opencode", false) => uninstall_opencode()?,
        ("gemini", true) => install_gemini()?,
        ("gemini", false) => uninstall_gemini()?,
        _ => return Err(format!("Unknown integration: {name}")),
    }
    status()
}

fn taskforce_home() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".taskforce")
}

fn opencode_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".config")
        .join("opencode")
        .join("plugins")
        .join("taskforce.js")
}

fn gemini_settings_path() -> PathBuf {
    dirs::home_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join(".gemini")
        .join("settings.json")
}

fn gemini_script_path() -> PathBuf {
    taskforce_home()
        .join("integrations")
        .join("gemini-hook.cjs")
}

fn install_opencode() -> Result<(), String> {
    let path = opencode_path();
    if path.exists() && !file_has_marker(&path) {
        return Err(format!(
            "Refusing to replace existing OpenCode plugin: {}",
            path.display()
        ));
    }
    write_file(&path, OPENCODE_PLUGIN)
}

fn uninstall_opencode() -> Result<(), String> {
    let path = opencode_path();
    if file_has_marker(&path) {
        fs::remove_file(path).map_err(display_error)?;
    }
    Ok(())
}

fn install_gemini() -> Result<(), String> {
    let script_path = gemini_script_path();
    write_file(&script_path, GEMINI_HOOK)?;

    let settings_path = gemini_settings_path();
    let backup_path = settings_path.with_extension("taskforce-backup.json");
    copy_backup(&settings_path, &backup_path).map_err(display_error)?;
    let mut settings = read_json_object(&settings_path)?;
    remove_taskforce_hook(&mut settings);

    let after_agent = settings
        .as_object_mut()
        .expect("settings root was validated")
        .entry("hooks")
        .or_insert_with(|| json!({}))
        .as_object_mut()
        .ok_or("Gemini settings 'hooks' value must be an object")?
        .entry("AfterAgent")
        .or_insert_with(|| json!([]))
        .as_array_mut()
        .ok_or("Gemini settings 'hooks.AfterAgent' value must be an array")?;

    let command_path = script_path.display().to_string().replace('"', "\\\"");
    after_agent.push(json!({
        "matcher": "",
        "hooks": [{
            "name": GEMINI_HOOK_NAME,
            "type": "command",
            "command": format!("node \"{command_path}\""),
            "timeout": 1000,
            "description": "Send agent completion events to Taskforce"
        }]
    }));
    write_json(&settings_path, &settings)
}

fn uninstall_gemini() -> Result<(), String> {
    let settings_path = gemini_settings_path();
    if settings_path.exists() {
        let mut settings = read_json_object(&settings_path)?;
        remove_taskforce_hook(&mut settings);
        write_json(&settings_path, &settings)?;
    }

    let script_path = gemini_script_path();
    if file_has_marker(&script_path) {
        fs::remove_file(script_path).map_err(display_error)?;
    }
    Ok(())
}

fn gemini_is_installed() -> Result<bool, String> {
    let path = gemini_settings_path();
    if !path.exists() || !file_has_marker(&gemini_script_path()) {
        return Ok(false);
    }
    let settings = read_json_object(&path)?;
    Ok(has_taskforce_hook(&settings))
}

fn has_taskforce_hook(settings: &Value) -> bool {
    settings
        .get("hooks")
        .and_then(|hooks| hooks.get("AfterAgent"))
        .and_then(Value::as_array)
        .is_some_and(|definitions| {
            definitions.iter().any(|definition| {
                definition
                    .get("hooks")
                    .and_then(Value::as_array)
                    .is_some_and(|hooks| {
                        hooks.iter().any(|hook| {
                            hook.get("name").and_then(Value::as_str) == Some(GEMINI_HOOK_NAME)
                        })
                    })
            })
        })
}

fn remove_taskforce_hook(settings: &mut Value) {
    let Some(definitions) = settings
        .get_mut("hooks")
        .and_then(|hooks| hooks.get_mut("AfterAgent"))
        .and_then(Value::as_array_mut)
    else {
        return;
    };

    definitions.retain(|definition| {
        !definition
            .get("hooks")
            .and_then(Value::as_array)
            .is_some_and(|hooks| {
                hooks
                    .iter()
                    .any(|hook| hook.get("name").and_then(Value::as_str) == Some(GEMINI_HOOK_NAME))
            })
    });
}

fn read_json_object(path: &Path) -> Result<Value, String> {
    if !path.exists() {
        return Ok(json!({}));
    }
    let contents = fs::read_to_string(path).map_err(display_error)?;
    let value: Value = serde_json::from_str(&contents)
        .map_err(|error| format!("Invalid JSON in {}: {error}", path.display()))?;
    if !value.is_object() {
        return Err(format!("{} must contain a JSON object", path.display()));
    }
    Ok(value)
}

fn write_json(path: &Path, value: &Value) -> Result<(), String> {
    let contents = serde_json::to_string_pretty(value).map_err(display_error)?;
    write_file(path, &format!("{contents}\n"))
}

fn write_file(path: &Path, contents: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(display_error)?;
    }
    fs::write(path, contents).map_err(display_error)
}

fn file_has_marker(path: &Path) -> bool {
    fs::read_to_string(path)
        .map(|contents| contents.contains(MARKER))
        .unwrap_or(false)
}

fn display_error(error: impl std::fmt::Display) -> String {
    error.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn removes_only_the_taskforce_hook() {
        let mut settings = json!({
            "hooks": {
                "AfterAgent": [
                    {"hooks": [{"name": GEMINI_HOOK_NAME}]},
                    {"hooks": [{"name": "keep-me"}]}
                ]
            }
        });
        remove_taskforce_hook(&mut settings);
        let remaining = settings["hooks"]["AfterAgent"].as_array().unwrap();
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0]["hooks"][0]["name"], "keep-me");
    }
}
