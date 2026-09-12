import { invoke } from "@tauri-apps/api/core";
import type { AppSettings, IntegrationStatus } from "./types";
import "./styles.css";

const root = document.querySelector<HTMLDivElement>("#app");

if (!root) {
  throw new Error("Taskforce application root was not found");
}

root.innerHTML = `
  <main class="settings-shell">
    <header class="masthead">
      <div class="brand-mark" aria-hidden="true">
        <span class="brand-eye brand-eye-left"></span>
        <span class="brand-eye brand-eye-right"></span>
      </div>
      <div>
        <p class="eyebrow">AGENT COMPLETION SIGNAL</p>
        <h1>Taskforce</h1>
      </div>
      <span class="daemon-state"><i></i> listening</span>
    </header>

    <section class="preview-panel">
      <div class="preview-copy">
        <span class="section-index">01 / SIGNAL</span>
        <h2>Your agent finished.<br />You should know.</h2>
        <p>A small character appears over whatever you are doing, rings once, then gets out of the way.</p>
        <div class="button-row">
          <button id="test-signal" class="button button-primary">Test signal</button>
          <button id="position-signal" class="button button-secondary">Position character</button>
        </div>
      </div>
      <div class="mascot-stage" aria-label="Taskforce character preview">
        <img src="/taskforce-mascot.gif" alt="Animated Taskforce signal character" />
        <span class="stage-line"></span>
      </div>
    </section>

    <section class="control-grid">
      <article class="control-panel">
        <span class="section-index">02 / BEHAVIOUR</span>
        <label class="range-label" for="duration">
          Display time
          <output id="duration-output">4.0 sec</output>
        </label>
        <input id="duration" type="range" min="1500" max="10000" step="500" />

        <label class="range-label" for="volume">
          Signal volume
          <output id="volume-output">70%</output>
        </label>
        <input id="volume" type="range" min="0" max="1" step="0.05" />

        <label class="switch-row">
          <span><strong>Play sound</strong><small>Original two-note signal</small></span>
          <input id="sound-enabled" type="checkbox" />
          <i aria-hidden="true"></i>
        </label>

        <label class="switch-row">
          <span><strong>Start at login</strong><small>Keep Taskforce ready in the tray</small></span>
          <input id="start-at-login" type="checkbox" />
          <i aria-hidden="true"></i>
        </label>
      </article>

      <article class="control-panel integrations-panel">
        <span class="section-index">03 / CONNECTIONS</span>
        <div class="integration-row">
          <div class="tool-icon">OC</div>
          <span><strong>OpenCode CLI</strong><small>Signals on session.idle</small></span>
          <button class="integration-toggle" data-integration="opencode">Checking</button>
        </div>
        <div class="integration-row">
          <div class="tool-icon gemini">G</div>
          <span><strong>Gemini CLI</strong><small>Signals after each agent turn</small></span>
          <button class="integration-toggle" data-integration="gemini">Checking</button>
        </div>
        <p class="privacy-note">Only the tool name, event type, and session identifier stay on this machine. Prompt and response content are never read.</p>
      </article>
    </section>

    <footer>
      <span id="status-message" role="status">Settings are stored locally.</span>
      <button id="save-settings" class="button button-primary">Save settings</button>
    </footer>
  </main>
`;

const durationInput = getElement<HTMLInputElement>("duration");
const volumeInput = getElement<HTMLInputElement>("volume");
const soundInput = getElement<HTMLInputElement>("sound-enabled");
const autostartInput = getElement<HTMLInputElement>("start-at-login");
const durationOutput = getElement<HTMLOutputElement>("duration-output");
const volumeOutput = getElement<HTMLOutputElement>("volume-output");
const statusMessage = getElement<HTMLSpanElement>("status-message");
const integrationButtons = Array.from(
  document.querySelectorAll<HTMLButtonElement>(".integration-toggle"),
);

let settings: AppSettings;
let integrations: IntegrationStatus = { opencode: false, gemini: false };

function getElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Missing element: ${id}`);
  return element as T;
}

function updateOutputs(): void {
  durationOutput.value = `${(Number(durationInput.value) / 1000).toFixed(1)} sec`;
  volumeOutput.value = `${Math.round(Number(volumeInput.value) * 100)}%`;
}

function readForm(): AppSettings {
  return {
    ...settings,
    durationMs: Number(durationInput.value),
    volume: Number(volumeInput.value),
    soundEnabled: soundInput.checked,
    startAtLogin: autostartInput.checked,
  };
}

function renderIntegrations(): void {
  for (const button of integrationButtons) {
    const name = button.dataset.integration as keyof IntegrationStatus;
    const enabled = integrations[name];
    button.textContent = enabled ? "Enabled" : "Enable";
    button.classList.toggle("enabled", enabled);
    button.disabled = false;
  }
}

function setStatus(message: string, isError = false): void {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

async function load(): Promise<void> {
  try {
    [settings, integrations] = await Promise.all([
      invoke<AppSettings>("get_settings"),
      invoke<IntegrationStatus>("get_integration_status"),
    ]);
    durationInput.value = String(settings.durationMs);
    volumeInput.value = String(settings.volume);
    soundInput.checked = settings.soundEnabled;
    autostartInput.checked = settings.startAtLogin;
    updateOutputs();
    renderIntegrations();
  } catch (error) {
    setStatus(String(error), true);
  }
}

durationInput.addEventListener("input", updateOutputs);
volumeInput.addEventListener("input", updateOutputs);
for (const input of [durationInput, volumeInput]) {
  input.addEventListener("wheel", (e) => e.preventDefault(), { passive: false });
}

getElement<HTMLButtonElement>("save-settings").addEventListener("click", async () => {
  try {
    settings = await invoke<AppSettings>("save_settings", { settings: readForm() });
    setStatus("Settings saved.");
  } catch (error) {
    setStatus(String(error), true);
  }
});

getElement<HTMLButtonElement>("test-signal").addEventListener("click", async () => {
  try {
    settings = await invoke<AppSettings>("save_settings", { settings: readForm() });
    await invoke("test_signal");
    setStatus("Test signal sent.");
  } catch (error) {
    setStatus(String(error), true);
  }
});

const positionButton = getElement<HTMLButtonElement>("position-signal");
let positioning = false;
positionButton.addEventListener("click", async () => {
  try {
    if (positioning) {
      settings = await invoke<AppSettings>("finish_positioning");
      positionButton.textContent = "Position character";
      setStatus("Character position saved.");
    } else {
      await invoke("start_positioning");
      positionButton.textContent = "Finish positioning";
      setStatus("Drag the character, then finish positioning.");
    }
    positioning = !positioning;
  } catch (error) {
    setStatus(String(error), true);
  }
});

for (const button of integrationButtons) {
  button.addEventListener("click", async () => {
    const name = button.dataset.integration as keyof IntegrationStatus;
    button.disabled = true;
    button.textContent = "Working";
    try {
      integrations = await invoke<IntegrationStatus>("set_integration", {
        name,
        enabled: !integrations[name],
      });
      renderIntegrations();
      setStatus(`${name === "opencode" ? "OpenCode" : "Gemini CLI"} integration updated.`);
    } catch (error) {
      renderIntegrations();
      setStatus(String(error), true);
    }
  });
}

void load();
