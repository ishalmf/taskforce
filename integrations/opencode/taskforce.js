// Taskforce desktop notifier plugin for OpenCode
import { spawn } from "node:child_process";
import { homedir } from "node:os";
import { join } from "node:path";

function notify(status, message) {
  try {
    const notifyBin = join(homedir(), ".local", "bin", "taskforce-notify");
    const args = ["--status", status];
    if (message) args.push("--message", message);
    spawn(notifyBin, args, {
      env: { ...process.env, DISPLAY: process.env.DISPLAY || ":0" },
      detached: true,
      stdio: "ignore",
    }).unref();
  } catch {
    // Non-blocking, never interrupt OpenCode
  }
}

export const TaskforcePlugin = async () => ({
  event: async ({ event }) => {
    // Fired when an assistant response (whether pure thinking/chat or tool calls) is 100% complete
    if (event.type === "session.idle") {
      notify("completed");
    } else if (event.type === "permission.updated" && event.properties?.status === "ask") {
      notify("help", "OpenCode needs your permission to proceed!");
    }
  },
});

export default TaskforcePlugin;
