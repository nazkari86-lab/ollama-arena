# CLI Reference

`ollama-arena` features a robust command-line interface with several subcommands to run matches, view leaderboards, and manage your local LLM evaluations.

## General Options

```bash
ollama-arena [OPTIONS] COMMAND [ARGS]...
```

* `--ollama URL`: Ollama backend URL (default: `http://localhost:11434`)
* `--backend URL|PRESET`: Custom OpenAI-compatible backend endpoint or preset (e.g. `vllm`, `lmstudio`, `openai`)
* `--api-key KEY`: API key for custom backend if required
* `--db PATH`: Path to SQLite database containing ratings and match history (default: `arena.db`)
* `--config PATH`: Path to configuration file (YAML/TOML/JSON). If not specified, searches in standard locations

---

## Configuration

ollama-arena supports configuration files to avoid repeating command-line arguments. Configuration files can be in YAML, TOML, or JSON format.

### Config File Locations

The CLI searches for configuration files in the following order:

1. Path specified via `--config` flag
2. `./ollama-arena.yaml` or `./ollama-arena.toml` (current directory)
3. `~/.ollama-arena/config.yaml` or `~/.ollama-arena/config.toml` (user directory)
4. `~/.config/ollama-arena/config.yaml` or `~/.config/ollama-arena/config.toml` (XDG standard)

### Config File Options

```yaml
# Example YAML configuration
ollama: "http://localhost:11434"
backend: null
api_key: null
db: "arena.db"
default_category: "coding"
default_difficulty: null
default_tasks: 10
dataset: null
dataset_limit: null
genome_db: "genome.db"
mcp_config: null
web_host: "0.0.0.0"
web_port: 7860
verbose: false
timeout: 120
```

See `.ollama-arena.yaml.example` and `.ollama-arena.toml.example` in the repository for complete examples.

### Config Commands

#### `config init`

Create a new configuration file.

```bash
ollama-arena config init [--path PATH] [--format yaml|toml|json]
```

* `--path PATH`: Path for the config file (default: `./ollama-arena.yaml`)
* `--format yaml|toml|json`: Configuration file format (default: `yaml`)

#### `config validate`

Validate the current configuration.

```bash
ollama-arena config validate [--config PATH] [--show]
```

* `--config PATH`: Path to config file to validate
* `--show`: Show configuration after validation

#### `config show`

Display the current configuration values.

```bash
ollama-arena config show [--config PATH] [--format yaml|json]
```

* `--config PATH`: Path to config file
* `--format yaml|json`: Output format (default: yaml)

### Precedence

Command-line arguments always override configuration file values. This allows you to set defaults in a config file and override them when needed.

Example:
```bash
# Config file has: default_tasks: 10
ollama-arena match --models A,B  # Uses 10 tasks from config
ollama-arena match --models A,B -n 20  # Overrides to 20 tasks
```

---

## Shell Autocomplete

ollama-arena provides shell autocomplete support for bash, zsh, and fish to improve your command-line experience.

### Installing Autocomplete

#### Automatic Installation

```bash
ollama-arena autocomplete install [--shell bash|zsh|fish] [--force]
```

* `--shell bash|zsh|fish`: Shell type (default: `bash`)
* `--force`: Overwrite existing completion file

#### Manual Installation

Generate the completion script and source it manually:

```bash
# Bash
ollama-arena autocomplete print --shell bash > ~/.bash_completion.d/ollama-arena
echo "source ~/.bash_completion.d/ollama-arena" >> ~/.bashrc
source ~/.bashrc

# Zsh
ollama-arena autocomplete print --shell zsh > ~/.zfunc/_ollama-arena
echo "fpath=(~/.zfunc \$fpath)" >> ~/.zshrc
echo "autoload -U compinit && compinit" >> ~/.zshrc
source ~/.zshrc

# Fish
ollama-arena autocomplete print --shell fish > ~/.config/fish/completions/ollama-arena.fish
# Fish loads completions automatically
```

### Autocomplete Features

- **Command completion**: Tab-complete all ollama-arena commands
- **Option completion**: Tab-complete command-specific options
- **Model completion**: Dynamic model name completion by querying the backend
- **Category completion**: Tab-complete task categories
- **Difficulty completion**: Tab-complete difficulty levels

Example usage:
```bash
$ ollama-arena mat<tab>  # Completes to "match"
$ ollama-arena match --cat<tab>  # Shows categories: coding, reasoning, security, ...
$ ollama-arena match --models lla<tab>  # Shows models: llama3.2:3b, llama3.1:8b, ...
```

---

## Commands

### `match`

Pits models head-to-head in automated battles.

```bash
ollama-arena match --models A,B --category coding -n 10
```

**Options:**
* `--models A,B`: Comma-separated list of models to match.
* `--category`: Task category to select (`coding`, `reasoning`, `security`, `planning`, `inspection`, `math`, `knowledge`, `creative`, `all`).
* `-n INT`: Number of tasks to run in this match (default: 10).
* `--verbose, -v`: Prints the full prompt, expected answer, and both model responses in real-time.
* `--share`: Outputs a shareable markdown table summarizing the match results.

### `benchmark`

Evaluates a model's performance on a standardized suite of tasks, giving a score from 0 to 100.

```bash
ollama-arena benchmark llama3.2:3b
```

**Options:**
* `--compare`: Provides a side-by-side comparison if two models are specified.
* `--fail-below SCORE`: Exits with code 1 if any model scores below the given score (useful for CI/CD pipelines).

### `leaderboard` (or `lb`)

Shows the ELO rating standings of all models evaluated.

```bash
ollama-arena leaderboard
```

### `results`

Browse recent matches and inspect their per-task results.

```bash
ollama-arena results
ollama-arena results --match <ID>
```

**Options:**
* `--match ID`: Shows details and responses for the specific match ID.
* `--last INT`: Number of recent matches to list (default: 10).
* `--full`: Print complete, untruncated prompts and responses.

### `inspect`

Shows all recorded runs/answers for a specific task ID across all models.

```bash
ollama-arena inspect math_001
```

### `report`

Analyzes a model's strengths and weaknesses across all categories based on match history.

```bash
ollama-arena report --model llama3.2:3b
```

### `publish`

Uploads the current ELO leaderboard, recent matches, benchmark history, and performance stats to a GitHub Gist.

```bash
ollama-arena publish
```

**Options:**
* `--public`: Makes the created Gist public.
* *Note: Requires `GITHUB_TOKEN` or `GH_TOKEN` environment variable to be set.*
