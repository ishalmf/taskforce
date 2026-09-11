use serde::{Deserialize, Serialize};
use std::sync::atomic::AtomicU64;
use std::{path::PathBuf, sync::Mutex};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SavedPosition {
    pub x: Option<i32>,
    pub y: Option<i32>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppSettings {
    pub duration_ms: u64,
    pub volume: f32,
    pub sound_enabled: bool,
    pub start_at_login: bool,
    pub position: SavedPosition,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            duration_ms: 4_000,
            volume: 0.7,
            sound_enabled: true,
            start_at_login: true,
            position: SavedPosition { x: None, y: None },
        }
    }
}

impl AppSettings {
    pub fn validated(mut self) -> Self {
        self.duration_ms = self.duration_ms.clamp(1_500, 10_000);
        self.volume = self.volume.clamp(0.0, 1.0);
        self
    }
}

pub struct AppState {
    pub settings: Mutex<AppSettings>,
    pub settings_path: PathBuf,
    pub sequence: AtomicU64,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SignalPayload {
    pub duration_ms: u64,
    pub volume: f32,
    pub sound_enabled: bool,
    pub sequence: u64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AgentEvent {
    pub version: u8,
    pub source: String,
    pub event: String,
    pub session_id: Option<String>,
    pub cwd: Option<String>,
    pub timestamp: Option<String>,
}

impl AgentEvent {
    pub fn is_completion(&self) -> bool {
        self.version == 1
            && self.event == "completed"
            && matches!(self.source.as_str(), "opencode" | "gemini")
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct IntegrationStatus {
    pub opencode: bool,
    pub gemini: bool,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn settings_are_clamped_to_safe_ranges() {
        let settings = AppSettings {
            duration_ms: 30,
            volume: 2.5,
            ..AppSettings::default()
        }
        .validated();

        assert_eq!(settings.duration_ms, 1_500);
        assert_eq!(settings.volume, 1.0);
    }

    #[test]
    fn only_known_completion_events_are_accepted() {
        let event = AgentEvent {
            version: 1,
            source: "opencode".into(),
            event: "completed".into(),
            session_id: None,
            cwd: None,
            timestamp: None,
        };
        assert!(event.is_completion());
    }
}
