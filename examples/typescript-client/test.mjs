// Runs index.mjs against a real `llmslim serve` on a free port with a temporary database, and checks its output.
// The server is started with LLMSLIM_PYTHON (default "python"), which needs `pip install "llmslim[server]"`.
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const python = process.env.LLMSLIM_PYTHON ?? "python";

const port = await new Promise((resolve, reject) => {
  const probe = createServer();
  probe.listen(0, "127.0.0.1", () => {
    const { port } = probe.address();
    probe.close(() => resolve(port));
  });
  probe.on("error", reject);
});
const folder = mkdtempSync(join(tmpdir(), "llmslim-example-"));
const server = spawn(python, ["-m", "llmslim.cli", "serve", "--port", String(port), "--db", join(folder, "memory.db")]);
let log = "";
server.stdout.on("data", (chunk) => (log += chunk));
server.stderr.on("data", (chunk) => (log += chunk));

const exited = new Promise((resolve) => server.once("exit", resolve));
let failed = false;
try {
  const baseUrl = `http://127.0.0.1:${port}`;
  let up = false;
  for (let attempt = 0; attempt < 300 && !up; attempt++) {
    try {
      up = (await fetch(`${baseUrl}/healthz`)).ok;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
  }
  if (!up) throw new Error(`llmslim serve did not start:\n${log}`);

  const run = spawnSync(process.execPath, ["index.mjs"], {
    cwd: fileURLToPath(new URL(".", import.meta.url)),
    env: { ...process.env, LLMSLIM_BASE_URL: baseUrl },
    encoding: "utf8",
  });
  process.stdout.write(run.stdout);
  process.stderr.write(run.stderr);
  if (run.status !== 0) throw new Error(`index.mjs exited with ${run.status}`);
  for (const expected of ["peanuts", "Pune", "test_refund_rounding FAILED"]) {
    if (!run.stdout.includes(expected)) throw new Error(`the output does not mention ${expected}`);
  }
  console.log("\nexample ok");
} catch (error) {
  console.error(error);
  failed = true;
} finally {
  server.kill();
  await exited; // so Windows releases the SQLite file before it is removed
  rmSync(folder, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
}
process.exit(failed ? 1 : 0);
