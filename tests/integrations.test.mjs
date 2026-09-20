import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawn } from "node:child_process";
import test from "node:test";

const repository = resolve(import.meta.dirname, "..");

async function createEndpoint(home, token = "test-token") {
  const received = new Promise((resolveRequest) => {
    const server = createServer((request, response) => {
      let body = "";
      request.setEncoding("utf8");
      request.on("data", (chunk) => {
        body += chunk;
      });
      request.on("end", () => {
        response.writeHead(204).end();
        server.close();
        resolveRequest({ request, body: JSON.parse(body) });
      });
    });
    server.listen(0, "127.0.0.1", async () => {
      const address = server.address();
      await mkdir(join(home, ".taskforce"), { recursive: true });
      await writeFile(
        join(home, ".taskforce", "endpoint.json"),
        JSON.stringify({ port: address.port, token }),
      );
    });
  });

  // Wait until endpoint.json has been written by the listening callback.
  while (true) {
    try {
      await import("node:fs/promises").then(({ access }) =>
        access(join(home, ".taskforce", "endpoint.json")),
      );
      break;
    } catch {
      await new Promise((resolveWait) => setTimeout(resolveWait, 5));
    }
  }
  return { received };
}

function runHook(path, input, home) {
  return new Promise((resolveRun, rejectRun) => {
    const child = spawn(process.execPath, [path], {
      env: { ...process.env, HOME: home, USERPROFILE: home },
      stdio: ["pipe", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk;
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk;
    });
    child.on("error", rejectRun);
    child.on("close", (code) => resolveRun({ code, stdout, stderr }));
    child.stdin.end(JSON.stringify(input));
  });
}

test("Gemini hook emits a private completion event and valid hook output", async () => {
  const home = await mkdtemp(join(tmpdir(), "taskforce-gemini-"));
  const { received } = await createEndpoint(home);
  const execution = runHook(
    join(repository, "integrations/gemini/taskforce-hook.cjs"),
    { session_id: "gemini-session", cwd: "/work", timestamp: "2026-01-01T00:00:00Z" },
    home,
  );
  const [{ request, body }, result] = await Promise.all([received, execution]);

  assert.equal(result.code, 0);
  assert.equal(result.stdout, "{}");
  assert.equal(result.stderr, "");
  assert.equal(request.headers.authorization, "Bearer test-token");
  assert.equal(body.source, "gemini");
  assert.equal(body.event, "completed");
  assert.equal(body.sessionId, "gemini-session");
});

test("OpenCode plugin filters subagents and triggers on root completion, cancellation, and questions", async () => {
  const home = await mkdtemp(join(tmpdir(), "taskforce-opencode-"));
  const previousHome = process.env.HOME;
  process.env.HOME = home;

  const binDir = join(home, ".local", "bin");
  await mkdir(binDir, { recursive: true });
  const logFile = join(home, "notify.log");
  const scriptPath = join(binDir, "taskforce-notify");
  await writeFile(
    scriptPath,
    `#!/bin/sh\necho "$@" >> "${logFile}"\n`,
    { mode: 0o755 },
  );

  const moduleUrl = new URL(
    `../integrations/opencode/taskforce.js?test=${Date.now()}`,
    import.meta.url,
  );
  const { TaskforcePlugin } = await import(moduleUrl);
  const plugin = await TaskforcePlugin({ directory: "/project" });

  const { readFile } = await import("node:fs/promises");

  // 1. Subagent creation and idle event must NOT trigger any popup
  await plugin.event({
    event: {
      type: "session.created",
      properties: {
        info: { id: "subagent-session-1", parentID: "root-session-1" },
      },
    },
  });
  await plugin.event({
    event: {
      type: "session.idle",
      properties: { sessionID: "subagent-session-1" },
    },
  });

  await new Promise((resolve) => setTimeout(resolve, 60));
  let logContent = await readFile(logFile, "utf8").catch(() => "");
  assert.equal(logContent, "", "Subagent completion should not trigger any notification");

  // 2. Question / permission requested triggers help popup
  await plugin.event({
    event: {
      type: "permission.asked",
      properties: { sessionID: "root-session-1", status: "ask" },
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 60));
  logContent = await readFile(logFile, "utf8").catch(() => "");
  assert.match(logContent, /--status help/);

  // 3. Cancelled/aborted turn triggers completion with cancel message
  await plugin.event({
    event: {
      type: "message.updated",
      properties: {
        sessionID: "root-session-1",
        info: {
          role: "assistant",
          error: { name: "MessageAbortedError", message: "Aborted" },
        },
      },
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 60));
  logContent = await readFile(logFile, "utf8").catch(() => "");
  assert.match(logContent, /Task was cancelled/);

  // 4. Root session completes its answer and goes idle
  await plugin.event({
    event: {
      type: "session.idle",
      properties: { sessionID: "root-session-1" },
    },
  });
  await new Promise((resolve) => setTimeout(resolve, 60));
  logContent = await readFile(logFile, "utf8").catch(() => "");
  assert.match(logContent, /--status completed/);

  process.env.HOME = previousHome;
});
