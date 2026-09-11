use crate::models::AppSettings;
use std::{fs, io, path::Path};

pub fn load_settings(path: &Path) -> AppSettings {
    fs::read_to_string(path)
        .ok()
        .and_then(|contents| serde_json::from_str(&contents).ok())
        .unwrap_or_default()
}

pub fn save_settings(path: &Path, settings: &AppSettings) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(display_error)?;
    }

    let temporary = path.with_extension("json.tmp");
    let contents = serde_json::to_vec_pretty(settings).map_err(display_error)?;
    fs::write(&temporary, contents).map_err(display_error)?;
    fs::rename(temporary, path).map_err(display_error)
}

pub fn write_private_json(path: &Path, value: &impl serde::Serialize) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(display_error)?;
    }
    let contents = serde_json::to_vec_pretty(value).map_err(display_error)?;
    fs::write(path, contents).map_err(display_error)?;

    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        fs::set_permissions(path, fs::Permissions::from_mode(0o600)).map_err(display_error)?;
    }
    Ok(())
}

fn display_error(error: impl std::fmt::Display) -> String {
    error.to_string()
}

pub fn copy_backup(path: &Path, backup: &Path) -> io::Result<()> {
    if path.exists() && !backup.exists() {
        fs::copy(path, backup)?;
    }
    Ok(())
}
