# CLI Enhancement Quick Start Guide

Quick reference for the new CLI configuration and autocomplete features in ollama-arena v2.5.0.

## Configuration Quick Start

### 1. Create a Config File

```bash
# Create a YAML config in current directory
ollama-arena config init

# Create a TOML config in a specific location
ollama-arena config init --path ~/.ollama-arena/config.toml --format toml
```

### 2. Edit Your Config

Edit the generated file with your preferences:

```yaml
# ollama-arena.yaml
ollama: "http://localhost:11434"
backend: null
db: "arena.db"
default_category: "coding"
default_tasks: 20  # Your preferred default
verbose: true
```

### 3. Use Config

The CLI automatically finds your config:

```bash
# Uses settings from config file
ollama-arena match --models llama3.2:3b,phi3

# Override specific settings when needed
ollama-arena match --models llama3.2:3b,phi3 -n 50
```

### 4. Validate Config

Check your config for errors:

```bash
ollama-arena config validate

# Show config after validation
ollama-arena config validate --show
```

### 5. View Current Config

See what config is being used:

```bash
ollama-arena config show

# View as JSON
ollama-arena config show --format json
```

## Autocomplete Quick Start

### Bash

```bash
# Install automatically
ollama-arena autocomplete install --shell bash

# Or manually
ollama-arena autocomplete print --shell bash > ~/.bash_completion.d/ollama-arena
echo "source ~/.bash_completion.d/ollama-arena" >> ~/.bashrc
source ~/.bashrc
```

### Zsh

```bash
# Install automatically
ollama-arena autocomplete install --shell zsh

# Or manually
ollama-arena autocomplete print --shell zsh > ~/.zfunc/_ollama-arena
echo "fpath=(~/.zfunc \$fpath)" >> ~/.zshrc
echo "autoload -U compinit && compinit" >> ~/.zshrc
source ~/.zshrc
```

### Fish

```bash
# Install automatically
ollama-arena autocomplete install --shell fish

# Fish loads completions automatically, no extra steps needed
```

## Using Autocomplete

After installation, use tab completion:

```bash
# Complete commands
ollama-arena mat<tab>  # → match

# Complete options
ollama-arena match --cat<tab>  # → --category

# Complete categories
ollama-arena match --category cod<tab>  # → coding

# Complete model names (dynamic!)
ollama-arena match --models lla<tab>  # → llama3.2:3b, llama3.1:8b, ...
```

## Config File Locations

The CLI searches for config files in this order:

1. `--config /path/to/config.yaml` (explicit path)
2. `./ollama-arena.yaml` (current directory)
3. `~/.ollama-arena/config.yaml` (user home)
4. `~/.config/ollama-arena/config.yaml` (XDG standard)

## Common Use Cases

### Project-Specific Config

```bash
# In your project directory
ollama-arena config init --path .ollama-arena.yaml
# Edit with project-specific settings
# All commands in this directory use this config
```

### Different Backends

```yaml
# ~/.ollama-arena/config.yaml
backend: "openai"
api_key: "sk-..."
```

```bash
ollama-arena match --models gpt-4,gpt-3.5-turbo
```

### CI/CD with Config

```yaml
# .github/workflows/benchmark.yml
- name: Benchmark models
  run: |
    ollama-arena config init --path config.yaml
    ollama-arena benchmark llama3.2:3b --fail-below 80
```

## Tips

1. **Start with defaults**: Use `config init` to get a working example
2. **Validate early**: Run `config validate` after editing
3. **Use autocomplete**: It saves time and prevents typos
4. **Project configs**: Keep project-specific settings in `./ollama-arena.yaml`
5. **Override when needed**: CLI args always override config values

## Troubleshooting

### Config Not Found

```bash
# Check which config is being used
ollama-arena config show

# Specify config explicitly
ollama-arena --config /path/to/config.yaml match --models ...
```

### Autocomplete Not Working

```bash
# Reinstall with force flag
ollama-arena autocomplete install --shell bash --force

# Reload your shell
source ~/.bashrc  # or ~/.zshrc
```

### Missing Dependencies

```bash
# Install with config support
pip install "ollama-arena[config]"
```

## More Information

- Full documentation: `docs/cli.md`
- Example configs: `.ollama-arena.yaml.example`, `.ollama-arena.toml.example`
- Enhancement summary: `CLI_ENHANCEMENT_SUMMARY.md`
