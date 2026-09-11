// Taskforce integration - managed by the Taskforce desktop application.
const { readFile } = require("node:fs/promises");
const { homedir } = require("node:os");
const { join } = require("node:path");

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", async () => {
  try {
    const hook = JSON.parse(input || "{}");
    const endpoint = JSON.parse(
      await readFile(join(homedir(), ".taskforce", "endpoint.json"), "utf8"),
    );
    await fetch(`http://127.0.0.1:${endpoint.port}/v1/events`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${endpoint.token}`,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        version: 1,
        source: "gemini",
        event: "completed",
        sessionId: hook.session_id ?? null,
        cwd: hook.cwd ?? null,
        timestamp: hook.timestamp ?? new Date().toISOString(),
      }),
      signal: AbortSignal.timeout(500),
    });
  } catch {
    // Hooks must remain silent and must not interfere with Gemini CLI.
  } finally {
    process.stdout.write("{}");
  }
});
