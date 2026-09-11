use crate::models::{AgentEvent, AppState, SignalPayload};
use crate::storage::write_private_json;
use serde::Serialize;
use std::io::Read;
use std::sync::atomic::Ordering;
use std::thread;
use std::time::Duration;
use tauri::{AppHandle, Emitter, Manager, PhysicalPosition};
use tiny_http::{Method, Response, Server, StatusCode};
use uuid::Uuid;

const MAX_EVENT_BYTES: u64 = 16 * 1024;

#[derive(Serialize)]
struct EndpointFile {
    port: u16,
    token: String,
}

pub fn start_event_server(app: AppHandle) -> Result<(), String> {
    let server = Server::http("127.0.0.1:0").map_err(|error| error.to_string())?;
    let port = server
        .server_addr()
        .to_ip()
        .ok_or("Taskforce event server did not bind to an IP address")?
        .port();
    let token = Uuid::new_v4().simple().to_string();
    let endpoint_path = dirs::home_dir()
        .ok_or("Unable to locate the user home directory")?
        .join(".taskforce")
        .join("endpoint.json");
    write_private_json(
        &endpoint_path,
        &EndpointFile {
            port,
            token: token.clone(),
        },
    )?;

    thread::spawn(move || {
        for mut request in server.incoming_requests() {
            let authorized = request.headers().iter().any(|header| {
                header.field.equiv("Authorization")
                    && header.value.as_str() == format!("Bearer {token}")
            });
            let valid_route = request.method() == &Method::Post && request.url() == "/v1/events";

            if !authorized || !valid_route {
                let _ = request.respond(Response::empty(StatusCode(401)));
                continue;
            }

            let mut body = String::new();
            let parsed = request
                .as_reader()
                .take(MAX_EVENT_BYTES)
                .read_to_string(&mut body)
                .ok()
                .and_then(|_| serde_json::from_str::<AgentEvent>(&body).ok());

            if parsed.as_ref().is_some_and(AgentEvent::is_completion) {
                show_signal(&app);
                let _ = request.respond(Response::empty(StatusCode(204)));
            } else {
                let _ = request.respond(Response::empty(StatusCode(400)));
            }
        }
    });

    Ok(())
}

pub fn show_signal(app: &AppHandle) {
    let state = app.state::<AppState>();
    let settings = state
        .settings
        .lock()
        .expect("Taskforce settings lock was poisoned")
        .clone();
    let sequence = state.sequence.fetch_add(1, Ordering::SeqCst) + 1;
    let Some(window) = app.get_webview_window("overlay") else {
        return;
    };

    position_overlay(&window, settings.position.x, settings.position.y);
    let _ = window.set_focusable(false);
    let _ = window.set_ignore_cursor_events(true);
    let _ = window.show();
    let _ = app.emit_to(
        "overlay",
        "taskforce://show",
        SignalPayload {
            duration_ms: settings.duration_ms,
            volume: settings.volume,
            sound_enabled: settings.sound_enabled,
            sequence,
        },
    );

    let app = app.clone();
    thread::spawn(move || {
        thread::sleep(Duration::from_millis(settings.duration_ms));
        let state = app.state::<AppState>();
        if state.sequence.load(Ordering::SeqCst) == sequence {
            if let Some(window) = app.get_webview_window("overlay") {
                let _ = window.hide();
            }
        }
    });
}

pub fn position_overlay(window: &tauri::WebviewWindow, x: Option<i32>, y: Option<i32>) {
    if let (Some(x), Some(y)) = (x, y) {
        let _ = window.set_position(PhysicalPosition::new(x, y));
        return;
    }

    if let Ok(Some(monitor)) = window.primary_monitor() {
        let monitor_position = monitor.position();
        let monitor_size = monitor.size();
        let x = monitor_position.x + monitor_size.width as i32 - 210;
        let y = monitor_position.y + monitor_size.height as i32 - 230;
        let _ = window.set_position(PhysicalPosition::new(x, y));
    }
}
