// Taskforce integration - managed by the Taskforce desktop application.
import { readFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";

async function sendCompletion(event, directory) {
  try {
    const endpointPath = join(homedir(), ".taskforce", "endpoint.json");
    const endpoint = JSON.parse(await readFile(endpointPath, "utf8"));
    await fetch(`http://127.0.0.1:${endpoint.port}/v1/events`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${endpoint.token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        version: 1,
        source: "opencode",
        event: "completed",
        sessionId: event.properties?.sessionID ?? null,
        cwd: directory,
        timestamp: new Date().toISOString(),
      }),
      signal: AbortSignal.timeout(500),
    });
  } catch {
    // Notifications must never interrupt the OpenCode session.
  }
}

export const TaskforcePlugin = async ({ directory }) => ({
  event: async ({ event }) => {
    if (event.type === "session.idle") await sendCompletion(event, directory);
  },
});
