import * as assert from "node:assert/strict";
import { test } from "node:test";
import {
  LLMSLIM_VERSION,
  MEMORY_DB_ENV,
  UVX_ARGS,
  findExecutable,
  manualConfig,
  resolveServer,
} from "../src/command";
import type { Host } from "../src/command";

function posixHost(files: string[], env: Record<string, string> = { PATH: "/usr/bin:/bin" }): Host {
  return { env, platform: "linux", homedir: "/home/asha", isFile: (file) => files.includes(file) };
}

function windowsHost(files: string[], env: Record<string, string>): Host {
  const lower = files.map((file) => file.toLowerCase());
  return {
    env,
    platform: "win32",
    homedir: "C:\\Users\\asha",
    isFile: (file) => lower.includes(file.toLowerCase()),
  };
}

test("runs the pinned release with uvx when uvx is on PATH", () => {
  const resolution = resolveServer({}, posixHost(["/usr/bin/uvx"]));
  assert.deepEqual(resolution, {
    ok: true,
    source: "uvx",
    command: "/usr/bin/uvx",
    args: ["--from", `llmslim[mcp]==${LLMSLIM_VERSION}`, "llmslim", "mcp"],
    env: {},
  });
});

test("the pin is an exact version", () => {
  assert.match(LLMSLIM_VERSION, /^\d+\.\d+\.\d+$/);
  assert.deepEqual(UVX_ARGS, ["--from", `llmslim[mcp]==${LLMSLIM_VERSION}`, "llmslim", "mcp"]);
});

test("finds uvx where uv's installer puts it when PATH lacks it", () => {
  const resolution = resolveServer({}, posixHost(["/home/asha/.local/bin/uvx"], { PATH: "/usr/bin" }));
  assert.equal(resolution.ok && resolution.command, "/home/asha/.local/bin/uvx");
});

test("reports a missing uvx", () => {
  assert.deepEqual(resolveServer({}, posixHost([])), { ok: false, reason: "uvx-not-found" });
});

test("the command setting wins over uvx and runs `<command> mcp`", () => {
  const host = posixHost(["/usr/bin/uvx", "/opt/venv/bin/llmslim"], { PATH: "/opt/venv/bin:/usr/bin" });
  assert.deepEqual(resolveServer({ command: "llmslim" }, host), {
    ok: true,
    source: "setting",
    command: "/opt/venv/bin/llmslim",
    args: ["mcp"],
    env: {},
  });
});

test("a command path is checked as given, with ~ expanded", () => {
  const host = posixHost(["/home/asha/.venvs/llmslim/bin/llmslim"]);
  const resolution = resolveServer({ command: " ~/.venvs/llmslim/bin/llmslim " }, host);
  assert.equal(resolution.ok && resolution.command, "/home/asha/.venvs/llmslim/bin/llmslim");
});

test("reports a command setting that can't be found, and does not fall back to uvx", () => {
  const host = posixHost(["/usr/bin/uvx"]);
  assert.deepEqual(resolveServer({ command: "/missing/llmslim" }, host), {
    ok: false,
    reason: "command-not-found",
    command: "/missing/llmslim",
  });
});

test("memoryPath reaches the server as LLMSLIM_MEMORY_DB, and an empty one is left out", () => {
  const host = posixHost(["/usr/bin/uvx"]);
  const set = resolveServer({ memoryPath: "/data/memory.db" }, host);
  assert.deepEqual(set.ok && set.env, { [MEMORY_DB_ENV]: "/data/memory.db" });
  assert.equal(MEMORY_DB_ENV, "LLMSLIM_MEMORY_DB");
  const empty = resolveServer({ memoryPath: "   " }, host);
  assert.deepEqual(empty.ok && empty.env, {});
});

test("on Windows, PATH is read case-insensitively and PATHEXT completes the name", () => {
  const host = windowsHost(["C:\\Users\\asha\\.local\\bin\\uvx.exe"], {
    Path: "C:\\Windows;C:\\Users\\asha\\.local\\bin",
    PATHEXT: ".COM;.EXE;.BAT;.CMD",
  });
  assert.equal(findExecutable("uvx", host), "C:\\Users\\asha\\.local\\bin\\uvx.exe");
  assert.equal(findExecutable("uvx.exe", host), "C:\\Users\\asha\\.local\\bin\\uvx.exe");
});

test("on Windows, a command path without .exe is completed", () => {
  const host = windowsHost(["C:\\venv\\Scripts\\llmslim.exe"], { Path: "C:\\Windows" });
  const resolution = resolveServer({ command: "C:\\venv\\Scripts\\llmslim" }, host);
  assert.equal(resolution.ok && resolution.command, "C:\\venv\\Scripts\\llmslim.exe");
});

test("the manual config runs the same pinned command", () => {
  assert.deepEqual(manualConfig(), { mcpServers: { llmslim: { command: "uvx", args: [...UVX_ARGS] } } });
});
