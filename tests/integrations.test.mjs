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

test("OpenCode plugin sends only session.idle events", async () => {
  const home = await mkdtemp(join(tmpdir(), "taskforce-opencode-"));
  const previousHome = process.env.HOME;
  process.env.HOME = home;
  const { received } = await createEndpoint(home);
  const moduleUrl = new URL(
    `../integrations/opencode/taskforce.js?test=${Date.now()}`,
    import.meta.url,
  );
  const { TaskforcePlugin } = await import(moduleUrl);
  const plugin = await TaskforcePlugin({ directory: "/project" });
  await plugin.event({ event: { type: "message.updated" } });
  await plugin.event({
    event: { type: "session.idle", properties: { sessionID: "open-session" } },
  });
  const { request, body } = await received;
  process.env.HOME = previousHome;

  assert.equal(request.headers.authorization, "Bearer test-token");
  assert.equal(body.source, "opencode");
  assert.equal(body.event, "completed");
  assert.equal(body.sessionId, "open-session");
  assert.equal(body.cwd, "/project");
});
