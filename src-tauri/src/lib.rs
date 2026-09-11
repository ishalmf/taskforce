mod integrations;
mod models;
mod signal;
mod storage;

use models::{AppSettings, AppState, IntegrationStatus};
use std::sync::atomic::AtomicU64;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{Emitter, Manager, RunEvent, WindowEvent};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

#[tauri::command]
fn get_settings(state: tauri::State<'_, AppState>) -> AppSettings {
    state
        .settings
        .lock()
        .expect("Taskforce settings lock was poisoned")
        .clone()
}

#[tauri::command]
fn save_settings(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
    settings: AppSettings,
) -> Result<AppSettings, String> {
    let settings = settings.validated();
    storage::save_settings(&state.settings_path, &settings)?;
    if settings.start_at_login {
        app.autolaunch()
            .enable()
            .map_err(|error| error.to_string())?;
    } else {
        app.autolaunch()
            .disable()
            .map_err(|error| error.to_string())?;
    }
    *state
        .settings
        .lock()
        .expect("Taskforce settings lock was poisoned") = settings.clone();
    Ok(settings)
}

#[tauri::command]
fn test_signal(app: tauri::AppHandle) {
    signal::show_signal(&app);
}

#[tauri::command]
fn start_positioning(app: tauri::AppHandle) -> Result<(), String> {
    let state = app.state::<AppState>();
    let settings = state
        .settings
        .lock()
        .expect("Taskforce settings lock was poisoned")
        .clone();
    let window = app
        .get_webview_window("overlay")
        .ok_or("Signal window is unavailable")?;
    signal::position_overlay(&window, settings.position.x, settings.position.y);
    window
        .set_focusable(true)
        .map_err(|error| error.to_string())?;
    window
        .set_ignore_cursor_events(false)
        .map_err(|error| error.to_string())?;
    window.show().map_err(|error| error.to_string())?;
    window.set_focus().map_err(|error| error.to_string())?;
    app.emit_to("overlay", "taskforce://positioning", true)
        .map_err(|error| error.to_string())
}

#[tauri::command]
fn save_overlay_position(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    let window = app
        .get_webview_window("overlay")
        .ok_or("Signal window is unavailable")?;
    let position = window.outer_position().map_err(|error| error.to_string())?;
    let mut settings = state
        .settings
        .lock()
        .expect("Taskforce settings lock was poisoned");
    settings.position.x = Some(position.x);
    settings.position.y = Some(position.y);
    storage::save_settings(&state.settings_path, &settings)
}

#[tauri::command]
fn finish_positioning(
    app: tauri::AppHandle,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    save_overlay_position(app.clone(), state)?;
    let window = app
        .get_webview_window("overlay")
        .ok_or("Signal window is unavailable")?;
    app.emit_to("overlay", "taskforce://positioning", false)
        .map_err(|error| error.to_string())?;
    window
        .set_ignore_cursor_events(true)
        .map_err(|error| error.to_string())?;
    window
        .set_focusable(false)
        .map_err(|error| error.to_string())?;
    window.hide().map_err(|error| error.to_string())
}

#[tauri::command]
fn get_integration_status() -> Result<IntegrationStatus, String> {
    integrations::status()
}

#[tauri::command]
fn set_integration(name: String, enabled: bool) -> Result<IntegrationStatus, String> {
    integrations::set(&name, enabled)
}

fn show_settings(app: &tauri::AppHandle) {
    if let Some(window) = app.get_webview_window("settings") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn create_tray(app: &tauri::App) -> tauri::Result<()> {
    let open = MenuItem::with_id(app, "open", "Open Taskforce", true, None::<&str>)?;
    let test = MenuItem::with_id(app, "test", "Test signal", true, None::<&str>)?;
    let quit = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&open, &test, &quit])?;
    let mut builder = TrayIconBuilder::new()
        .menu(&menu)
        .show_menu_on_left_click(true)
        .tooltip("Taskforce")
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_settings(app),
            "test" => signal::show_signal(app),
            "quit" => app.exit(0),
            _ => {}
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            show_settings(app);
        }))
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            Some(vec!["--background"]),
        ))
        .invoke_handler(tauri::generate_handler![
            get_settings,
            save_settings,
            test_signal,
            start_positioning,
            save_overlay_position,
            finish_positioning,
            get_integration_status,
            set_integration
        ])
        .setup(|app| {
            let settings_path = app.path().app_config_dir()?.join("settings.json");
            let settings = storage::load_settings(&settings_path).validated();
            let start_at_login = settings.start_at_login;
            app.manage(AppState {
                settings: std::sync::Mutex::new(settings),
                settings_path,
                sequence: AtomicU64::new(0),
            });

            create_tray(app)?;
            signal::start_event_server(app.handle().clone())
                .map_err(|error| std::io::Error::other(error))?;

            if let Some(overlay) = app.get_webview_window("overlay") {
                let _ = overlay.set_ignore_cursor_events(true);
                let _ = overlay.set_visible_on_all_workspaces(true);
            }

            if start_at_login {
                let _ = app.autolaunch().enable();
            }

            if !std::env::args().any(|argument| argument == "--background") {
                show_settings(app.handle());
            }

            if let Some(settings_window) = app.get_webview_window("settings") {
                let window = settings_window.clone();
                settings_window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = window.hide();
                    }
                });
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Taskforce");

    app.run(|_, event| {
        if matches!(event, RunEvent::ExitRequested { .. }) {
            // The tray menu controls the application lifetime.
        }
    });
}
