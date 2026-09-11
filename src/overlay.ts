import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import type { SignalPayload } from "./types";
import "./overlay.css";

const root = document.querySelector<HTMLDivElement>("#app");

if (!root) {
  throw new Error("Taskforce overlay root was not found");
}

root.innerHTML = `
  <div id="signal-character" class="signal-character" aria-hidden="true">
    <img id="mascot" src="/taskforce-mascot.gif" alt="" draggable="false" />
  </div>
`;

const character = document.getElementById("signal-character") as HTMLDivElement;
const mascot = document.getElementById("mascot") as HTMLImageElement;
const overlayWindow = getCurrentWindow();
let sound: HTMLAudioElement | null = null;

function play(payload: SignalPayload): void {
  character.classList.remove("is-playing");
  mascot.src = "";
  void character.offsetWidth;
  mascot.src = `/taskforce-mascot.gif?signal=${payload.sequence}`;
  character.classList.add("is-playing");

  if (payload.soundEnabled && payload.volume > 0) {
    sound?.pause();
    sound = new Audio("/taskforce-chime.wav");
    sound.volume = Math.min(1, Math.max(0, payload.volume));
    void sound.play().catch(() => undefined);
  }
}

void listen<SignalPayload>("taskforce://show", ({ payload }) => play(payload));
void listen<boolean>("taskforce://positioning", ({ payload }) => {
  document.body.classList.toggle("positioning", payload);
  if (payload) character.classList.add("is-playing");
});

character.addEventListener("pointerdown", async (event) => {
  if (!document.body.classList.contains("positioning") || event.button !== 0) return;
  try {
    await overlayWindow.startDragging();
    await invoke("save_overlay_position");
  } catch {
    // Positioning support depends on the host compositor.
  }
});
