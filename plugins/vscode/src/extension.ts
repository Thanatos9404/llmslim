import * as fs from "node:fs";
import * as os from "node:os";
import * as vscode from "vscode";
import { LLMSLIM_VERSION, UVX_ARGS, manualConfig, resolveServer } from "./command";
import type { Host, Resolution, Settings } from "./command";

/** Must match `contributes.mcpServerDefinitionProviders[].id` in package.json. */
const PROVIDER_ID = "llmslim";
const SERVER_LABEL = "LLMSlim Memory";
const UV_INSTALL_URL = "https://docs.astral.sh/uv/getting-started/installation/";
const SETUP_GUIDE_URL = "https://github.com/Thanatos9404/llmslim/blob/main/docs/MCP.md";
const UNSUPPORTED_NOTICE_KEY = "llmslim.unsupportedEditorNoticeShown";

function localHost(): Host {
  return {
    env: process.env,
    platform: process.platform,
    homedir: os.homedir(),
    isFile: (file) => {
      try {
        return fs.statSync(file).isFile();
      } catch {
        return false;
      }
    },
  };
}

function readSettings(): Settings {
  const config = vscode.workspace.getConfiguration("llmslim");
  return {
    command: config.get<string>("command", ""),
    memoryPath: config.get<string>("memoryPath", ""),
  };
}

/**
 * The server as VS Code lists it. When the command can't be found yet, the server is still listed (with the command
 * as configured) so the user sees it; resolveMcpServerDefinition explains what is missing when it is started.
 */
function serverDefinition(resolution: Resolution, settings: Settings): vscode.McpStdioServerDefinition {
  if (resolution.ok) {
    const version = resolution.source === "uvx" ? LLMSLIM_VERSION : undefined;
    return new vscode.McpStdioServerDefinition(
      SERVER_LABEL,
      resolution.command,
      resolution.args,
      resolution.env,
      version,
    );
  }
  const override = settings.command?.trim();
  return override
    ? new vscode.McpStdioServerDefinition(SERVER_LABEL, override, ["mcp"])
    : new vscode.McpStdioServerDefinition(SERVER_LABEL, "uvx", [...UVX_ARGS], {}, LLMSLIM_VERSION);
}

async function explainMissingCommand(resolution: Exclude<Resolution, { ok: true }>): Promise<void> {
  if (resolution.reason === "uvx-not-found") {
    const installUv = "Install uv";
    const usePip = "Use pip instead";
    const choice = await vscode.window.showWarningMessage(
      "LLMSlim Memory runs its MCP server with uvx, which was not found. Install uv (https://docs.astral.sh/uv/) " +
        "and start the server again. Or run pip install \"llmslim[mcp]\" (Python 3.10 or newer) and set the " +
        "LLMSlim: Command setting to llmslim, so the server starts as llmslim mcp.",
      installUv,
      usePip,
    );
    if (choice === installUv) {
      await vscode.env.openExternal(vscode.Uri.parse(UV_INSTALL_URL));
    } else if (choice === usePip) {
      await vscode.commands.executeCommand("workbench.action.openSettings", "llmslim.command");
    }
    return;
  }
  const openSettings = "Open Settings";
  const choice = await vscode.window.showWarningMessage(
    `LLMSlim Memory could not find "${resolution.command}", set in LLMSlim: Command. Check the path, or clear the ` +
      "setting to run the server with uvx.",
    openSettings,
  );
  if (choice === openSettings) {
    await vscode.commands.executeCommand("workbench.action.openSettings", "llmslim.command");
  }
}

/** Editors built on VS Code that don't have its MCP extension API get the config to add by hand, once. */
async function explainUnsupportedEditor(context: vscode.ExtensionContext): Promise<void> {
  if (context.globalState.get<boolean>(UNSUPPORTED_NOTICE_KEY)) {
    return;
  }
  await context.globalState.update(UNSUPPORTED_NOTICE_KEY, true);
  const copyConfig = "Copy MCP config";
  const openGuide = "Open setup guide";
  const choice = await vscode.window.showInformationMessage(
    "This editor does not support VS Code's MCP extension API (VS Code 1.101 or newer has it), so LLMSlim Memory " +
      "could not add its server. Add it in the editor's own MCP settings instead.",
    copyConfig,
    openGuide,
  );
  if (choice === copyConfig) {
    await vscode.env.clipboard.writeText(JSON.stringify(manualConfig(), null, 2));
  } else if (choice === openGuide) {
    await vscode.env.openExternal(vscode.Uri.parse(SETUP_GUIDE_URL));
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const lm = vscode.lm as Partial<typeof vscode.lm> | undefined;
  if (typeof lm?.registerMcpServerDefinitionProvider !== "function") {
    void explainUnsupportedEditor(context);
    return;
  }

  const didChange = new vscode.EventEmitter<void>();
  context.subscriptions.push(
    didChange,
    vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("llmslim")) {
        didChange.fire();
      }
    }),
    vscode.lm.registerMcpServerDefinitionProvider(PROVIDER_ID, {
      onDidChangeMcpServerDefinitions: didChange.event,
      provideMcpServerDefinitions: () => {
        const settings = readSettings();
        return [serverDefinition(resolveServer(settings, localHost()), settings)];
      },
      resolveMcpServerDefinition: (server) => {
        // Look again at start time: uv may have been installed since the server was listed.
        const resolution = resolveServer(readSettings(), localHost());
        if (!resolution.ok) {
          void explainMissingCommand(resolution);
          return undefined;
        }
        if ("command" in server) {
          server.command = resolution.command;
          server.args = resolution.args;
          server.env = resolution.env;
        }
        return server;
      },
    }),
  );
}

export function deactivate(): void {}
