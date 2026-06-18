import * as vscode from 'vscode';
import axios, { AxiosInstance } from 'axios';

interface ArenaConfig {
  apiUrl: string;
  defaultModels: string[];
  defaultCategory: string;
  autoOpenResults: boolean;
}

interface MatchResult {
  id: string;
  model_a: string;
  model_b: string;
  winner: 'A' | 'B' | 'tie';
  score_a: number;
  score_b: number;
  task: string;
  category: string;
  timestamp: string;
}

interface LeaderboardEntry {
  rank: number;
  model: string;
  elo: number;
  wins: number;
  losses: number;
  draws: number;
  win_rate: number;
}

class ArenaClient {
  private client: AxiosInstance;
  private config: ArenaConfig;

  constructor(config: ArenaConfig) {
    this.config = config;
    this.client = axios.create({
      baseURL: config.apiUrl,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 30000,
    });
  }

  async sendCodeForBattle(
    code: string,
    language: string,
    models?: string[],
    category?: string
  ): Promise<string> {
    try {
      const response = await this.client.post('/match', {
        code,
        language,
        models: models || this.config.defaultModels,
        category: category || this.config.defaultCategory,
        n: 1,
      });
      return response.data.job_id;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Arena API error: ${error.message}`);
      }
      throw error;
    }
  }

  async getJobStatus(jobId: string): Promise<any> {
    try {
      const response = await this.client.get(`/job/${jobId}`);
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Arena API error: ${error.message}`);
      }
      throw error;
    }
  }

  async getLeaderboard(): Promise<LeaderboardEntry[]> {
    try {
      const response = await this.client.get('/leaderboard');
      return response.data;
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Arena API error: ${error.message}`);
      }
      throw error;
    }
  }

  async getModels(): Promise<string[]> {
    try {
      const response = await this.client.get('/models');
      return response.data.map((m: any) => m.name);
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw new Error(`Arena API error: ${error.message}`);
      }
      throw error;
    }
  }
}

class ArenaLeaderboardProvider implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  private client: ArenaClient;

  constructor(client: ArenaClient) {
    this.client = client;
  }

  public resolveWebviewView(
    webviewView: vscode.WebviewView,
    context: vscode.WebviewViewResolveContext,
    _token: vscode.CancellationToken
  ) {
    this._view = webviewView;

    webviewView.webview.options = {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')],
    };

    webviewView.webview.html = this.getHtmlContent();

    this.updateLeaderboard();

    webviewView.onDidChangeVisibility(() => {
      if (webviewView.visible) {
        this.updateLeaderboard();
      }
    });
  }

  private async updateLeaderboard() {
    try {
      const leaderboard = await this.client.getLeaderboard();
      if (this._view) {
        this._view.webview.html = this.getHtmlContent(leaderboard);
      }
    } catch (error) {
      vscode.window.showErrorMessage(`Failed to load leaderboard: ${error}`);
    }
  }

  private getHtmlContent(leaderboard?: LeaderboardEntry[]): string {
    return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Arena Leaderboard</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      padding: 10px;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
    }
    table {
      width: 100%;
      border-collapse: collapse;
    }
    th, td {
      text-align: left;
      padding: 8px;
      border-bottom: 1px solid var(--vscode-panel-border);
    }
    th {
      font-weight: bold;
      color: var(--vscode-foreground);
    }
    .rank-1 { color: #ffd700; }
    .rank-2 { color: #c0c0c0; }
    .rank-3 { color: #cd7f32; }
  </style>
</head>
<body>
  <h2>🏆 Arena Leaderboard</h2>
  ${leaderboard ? `
    <table>
      <thead>
        <tr>
          <th>Rank</th>
          <th>Model</th>
          <th>ELO</th>
          <th>Win Rate</th>
        </tr>
      </thead>
      <tbody>
        ${leaderboard.map(entry => `
          <tr>
            <td class="rank-${entry.rank}">${entry.rank}</td>
            <td>${entry.model}</td>
            <td>${entry.elo.toFixed(0)}</td>
            <td>${entry.win_rate.toFixed(1)}%</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  ` : '<p>Loading...</p>'}
</body>
</html>`;
  }
}

export function activate(context: vscode.ExtensionContext) {
  console.log('Ollama Arena Extension is now active');

  // Get configuration
  const config = vscode.workspace.getConfiguration('ollamaArena');
  const arenaConfig: ArenaConfig = {
    apiUrl: config.get('apiUrl', 'http://localhost:7860/api'),
    defaultModels: config.get('defaultModels', ['llama3.2:3b', 'qwen2.5:7b']),
    defaultCategory: config.get('defaultCategory', 'coding'),
    autoOpenResults: config.get('autoOpenResults', true),
  };

  // Create arena client
  const arenaClient = new ArenaClient(arenaConfig);

  // Register leaderboard provider
  const leaderboardProvider = new ArenaLeaderboardProvider(arenaClient);
  context.subscriptions.push(
    vscode.window.registerWebviewViewProvider('ollama-arena.leaderboard', leaderboardProvider)
  );

  // Send to Arena command
  const sendToArenaCommand = vscode.commands.registerCommand(
    'ollama-arena.sendToArena',
    async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
      }

      const selection = editor.selection;
      const selectedText = editor.document.getText(selection);
      const language = editor.document.languageId;

      if (!selectedText) {
        vscode.window.showWarningMessage('No text selected');
        return;
      }

      // Show configuration options
      const models = await vscode.window.showQuickPick(
        arenaClient.getModels(),
        {
          placeHolder: 'Select models to compete',
          canPickMany: true,
        }
      );

      if (!models || models.length === 0) {
        return;
      }

      const categories = [
        'coding', 'reasoning', 'security', 'planning', 'inspection',
        'math', 'knowledge', 'creative', 'json_format', 'tool_use', 'vision', 'all'
      ];
      const category = await vscode.window.showQuickPick(categories, {
        placeHolder: 'Select task category',
      });

      if (!category) {
        return;
      }

      try {
        await vscode.window.withProgress(
          {
            location: vscode.ProgressLocation.Notification,
            title: 'Sending code to Arena...',
            cancellable: false,
          },
          async (progress) => {
            progress.report({ increment: 0, message: 'Initializing battle...' });

            const jobId = await arenaClient.sendCodeForBattle(
              selectedText,
              language,
              models,
              category
            );

            progress.report({ increment: 50, message: `Battle started! Job ID: ${jobId}` });

            // Poll for job completion
            let jobStatus = await arenaClient.getJobStatus(jobId);
            while (jobStatus.status === 'pending' || jobStatus.status === 'running') {
              await new Promise(resolve => setTimeout(resolve, 2000));
              jobStatus = await arenaClient.getJobStatus(jobId);
              progress.report({
                increment: Math.min(jobStatus.progress || 0, 100),
                message: `Battle in progress... ${jobStatus.progress || 0}%`
              });
            }

            progress.report({ increment: 100, message: 'Battle complete!' });

            if (jobStatus.status === 'completed' && arenaConfig.autoOpenResults) {
              // Show results in a new webview panel
              const panel = vscode.window.createWebviewPanel(
                'arenaResults',
                'Arena Battle Results',
                vscode.ViewColumn.One,
                { enableScripts: true }
              );

              panel.webview.html = getResultsHtml(jobStatus.result);
            } else if (jobStatus.status === 'failed') {
              vscode.window.showErrorMessage(`Battle failed: ${jobStatus.error}`);
            }
          }
        );
      } catch (error) {
        vscode.window.showErrorMessage(`Failed to send to Arena: ${error}`);
      }
    }
  );

  // Start Battle command
  const startBattleCommand = vscode.commands.registerCommand(
    'ollama-arena.startBattle',
    async () => {
      // Quick action to start a battle with default settings
      vscode.commands.executeCommand('ollama-arena.sendToArena');
    }
  );

  // Show Leaderboard command
  const showLeaderboardCommand = vscode.commands.registerCommand(
    'ollama-arena.showLeaderboard',
    () => {
      vscode.commands.executeCommand('workbench.view.extension.ollama-arena');
    }
  );

  // Configure Arena command
  const configureCommand = vscode.commands.registerCommand(
    'ollama-arena.configureArena',
    async () => {
      await vscode.commands.executeCommand('workbench.action.openSettings', 'ollamaArena');
    }
  );

  context.subscriptions.push(
    sendToArenaCommand,
    startBattleCommand,
    showLeaderboardCommand,
    configureCommand
  );
}

function getResultsHtml(results: any): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Arena Battle Results</title>
  <style>
    body {
      font-family: var(--vscode-font-family);
      padding: 20px;
      color: var(--vscode-foreground);
      background: var(--vscode-editor-background);
    }
    .result-card {
      background: var(--vscode-editor-inactiveSelectionBackground);
      padding: 15px;
      margin: 10px 0;
      border-radius: 5px;
      border: 1px solid var(--vscode-panel-border);
    }
    .winner {
      border: 2px solid #3fb950;
    }
    .winner-badge {
      background: #3fb950;
      color: white;
      padding: 2px 8px;
      border-radius: 3px;
      font-size: 12px;
    }
  </style>
</head>
<body>
  <h1>🏆 Arena Battle Results</h1>
  ${results ? `
    ${Object.entries(results).map(([model, result]: [string, any]) => `
      <div class="result-card ${result.winner ? 'winner' : ''}">
        <h2>
          ${model}
          ${result.winner ? '<span class="winner-badge">WINNER</span>' : ''}
        </h2>
        <p><strong>Score:</strong> ${result.score}</p>
        <p><strong>Response:</strong></p>
        <pre>${result.response || 'No response available'}</pre>
      </div>
    `).join('')}
  ` : '<p>No results available</p>'}
</body>
</html>`;
}

export function deactivate() {
  console.log('Ollama Arena Extension is now deactivated');
}