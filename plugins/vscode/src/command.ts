// How the extension starts the LLMSlim MCP server. This file does not import `vscode`, so the unit tests run under
// plain Node.

import * as path from "node:path";

/** The llmslim release the server runs. Bump it with each llmslim release (see RELEASE_CHECKLIST.md). */
export const LLMSLIM_VERSION = "0.11.2";

/** The package uvx installs: pinned, so every start runs the same release. */
export const PACKAGE_SPEC = `llmslim[mcp]==${LLMSLIM_VERSION}`;

/** `uvx --from "llmslim[mcp]==X.Y.Z" llmslim mcp` */
export const UVX_ARGS: readonly string[] = ["--from", PACKAGE_SPEC, "llmslim", "mcp"];

/** The environment variable `llmslim mcp` reads for its memory file (llmslim/mcp_server.py). */
export const MEMORY_DB_ENV = "LLMSLIM_MEMORY_DB";

/** The extension's settings, as the user wrote them. */
export interface Settings {
  /** `llmslim.command`: the llmslim executable to run instead of uvx. */
  command?: string;
  /** `llmslim.memoryPath`: the SQLite file for the memory. */
  memoryPath?: string;
}

/** What the resolver needs from the machine, so tests can pass a fake one. */
export interface Host {
  env: Record<string, string | undefined>;
  platform: NodeJS.Platform;
  homedir: string;
  isFile(file: string): boolean;
}

export type Resolution =
  | {
      ok: true;
      /** Where the command came from: the pinned uvx launcher, or the `llmslim.command` setting. */
      source: "uvx" | "setting";
      command: string;
      args: string[];
      env: Record<string, string>;
    }
  | { ok: false; reason: "uvx-not-found" }
  | { ok: false; reason: "command-not-found"; command: string };

function pathApi(host: Host): typeof path.posix {
  return host.platform === "win32" ? path.win32 : path.posix;
}

function getEnv(host: Host, name: string): string | undefined {
  if (host.platform !== "win32") {
    return host.env[name];
  }
  // Windows environment variable names are case-insensitive ("Path" or "PATH").
  const key = Object.keys(host.env).find((k) => k.toUpperCase() === name.toUpperCase());
  return key === undefined ? undefined : host.env[key];
}

function expandHome(file: string, host: Host): string {
  if (file === "~") {
    return host.homedir;
  }
  if (file.startsWith("~/") || (host.platform === "win32" && file.startsWith("~\\"))) {
    return pathApi(host).join(host.homedir, file.slice(2));
  }
  return file;
}

function extensions(name: string, host: Host): string[] {
  if (host.platform !== "win32") {
    return [""];
  }
  const pathext = (getEnv(host, "PATHEXT") || ".COM;.EXE;.BAT;.CMD")
    .split(";")
    .filter(Boolean)
    .map((ext) => ext.toLowerCase());
  const hasExtension = pathext.includes(path.win32.extname(name).toLowerCase());
  return hasExtension ? [""] : pathext;
}

/**
 * Directories where installers put uv when they don't add it to the PATH an editor started from the desktop sees:
 * uv's own installer (~/.local/bin), older uv installers (~/.cargo/bin) and Homebrew on macOS.
 */
function fallbackDirectories(host: Host): string[] {
  const api = pathApi(host);
  const directories = [api.join(host.homedir, ".local", "bin"), api.join(host.homedir, ".cargo", "bin")];
  if (host.platform === "darwin") {
    directories.push("/opt/homebrew/bin", "/usr/local/bin");
  }
  return directories;
}

/**
 * Finds an executable the way a shell would: a path is checked as given (after `~` expansion), a bare name is looked
 * up on PATH and then in the usual uv install directories. Returns the full path, or undefined.
 */
export function findExecutable(name: string, host: Host): string | undefined {
  const api = pathApi(host);
  const expanded = expandHome(name, host);
  const exts = extensions(expanded, host);
  const isPath = expanded.includes("/") || (host.platform === "win32" && expanded.includes("\\"));
  if (isPath) {
    return exts.map((ext) => expanded + ext).find((candidate) => host.isFile(candidate));
  }
  const delimiter = host.platform === "win32" ? ";" : ":";
  const directories = (getEnv(host, "PATH") || "").split(delimiter).filter(Boolean);
  for (const directory of [...directories, ...fallbackDirectories(host)]) {
    for (const ext of exts) {
      const candidate = api.join(directory, expanded + ext);
      if (host.isFile(candidate)) {
        return candidate;
      }
    }
  }
  return undefined;
}

/**
 * Decides how to start the server. The `llmslim.command` setting wins; otherwise the pinned release runs with uvx.
 * `llmslim.memoryPath`, when set, reaches the server as LLMSLIM_MEMORY_DB.
 */
export function resolveServer(settings: Settings, host: Host): Resolution {
  const env: Record<string, string> = {};
  const memoryPath = settings.memoryPath?.trim();
  if (memoryPath) {
    env[MEMORY_DB_ENV] = memoryPath;
  }
  const override = settings.command?.trim();
  if (override) {
    const command = findExecutable(override, host);
    if (command === undefined) {
      return { ok: false, reason: "command-not-found", command: override };
    }
    return { ok: true, source: "setting", command, args: ["mcp"], env };
  }
  const uvx = findExecutable("uvx", host);
  if (uvx === undefined) {
    return { ok: false, reason: "uvx-not-found" };
  }
  return { ok: true, source: "uvx", command: uvx, args: [...UVX_ARGS], env };
}

/** The server entry to add by hand in editors that don't support VS Code's MCP extension API. */
export function manualConfig(): { mcpServers: { llmslim: { command: string; args: string[] } } } {
  return { mcpServers: { llmslim: { command: "uvx", args: [...UVX_ARGS] } } };
}
