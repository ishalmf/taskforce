// Taskforce desktop notifier plugin for OpenCode
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
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

let dbInstance = null;
async function getDb() {
  if (dbInstance) return dbInstance;
  try {
    const { DatabaseSync } = await import("node:sqlite");
    const dbPath = join(homedir(), ".local", "share", "opencode", "opencode.db");
    if (existsSync(dbPath)) {
      dbInstance = new DatabaseSync(dbPath, { readOnly: true });
    }
  } catch {
    // node:sqlite or db not available
  }
  return dbInstance;
}

const subagentSessions = new Set();

async function isSubagent(sessionId) {
  if (!sessionId) return false;
  if (subagentSessions.has(sessionId)) return true;

  try {
    const db = await getDb();
    if (db) {
      const stmt = db.prepare("SELECT parent_id FROM session WHERE id = ? LIMIT 1");
      const row = stmt.get(sessionId);
      if (row && row.parent_id) {
        subagentSessions.add(sessionId);
        return true;
      }
    }
  } catch {
    // Fallback if db query fails
  }
  return false;
}

export const TaskforcePlugin = async () => ({
  event: async ({ event }) => {
    if (!event) return;

    // Track subagent sessions when created
    if (event.type?.startsWith("session.created") && event.properties?.info?.parentID) {
      const subId = event.properties.info.id || event.properties.sessionID;
      if (subId) subagentSessions.add(subId);
    }

    const sessionId =
      event.properties?.sessionID ||
      event.properties?.info?.sessionID ||
      event.properties?.info?.id;

    // Filter out subagent sessions completely: only root agent completion triggers notification
    if (sessionId && (await isSubagent(sessionId))) {
      return;
    }

    // 1. Session Idle (Task completion for root agent)
    if (event.type === "session.idle") {
      notify("completed");
    }
    // 2. Cancellation / Abort
    else if (
      event.type === "session.error" &&
      (event.properties?.error?.name === "MessageAbortedError" ||
        String(event.properties?.error).toLowerCase().includes("abort") ||
        String(event.properties?.error).toLowerCase().includes("cancel"))
    ) {
      notify("completed", "Task was cancelled");
    } else if (
      event.type === "message.updated" &&
      event.properties?.info?.role === "assistant"
    ) {
      const err = event.properties?.info?.error;
      if (
        err &&
        (err.name === "MessageAbortedError" ||
          String(err).toLowerCase().includes("abort") ||
          String(err).toLowerCase().includes("cancel"))
      ) {
        notify("completed", "Task was cancelled");
      }
    }
    // 3. Needs permission / Question
    else if (
      (event.type?.startsWith("permission") &&
        (event.properties?.status === "ask" ||
          event.type === "permission.asked")) ||
      event.type?.startsWith("question")
    ) {
      notify("help", "OpenCode needs your answer / permission to proceed!");
    }
  },
});

export default TaskforcePlugin;
