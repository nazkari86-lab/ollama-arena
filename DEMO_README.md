# Demo Recording Instructions

This document explains how to create and process demo recordings for ollama-arena v2.5.0.

## Prerequisites

Install asciinema for terminal recording:
```bash
# macOS
brew install asciinema

# Linux
sudo apt install asciinema  # Ubuntu/Debian
sudo dnf install asciinema  # Fedora
```

Install terminal gif converter (optional):
```bash
# Using agg (asciinema to gif)
pip install agg

# Or using asciicast2gif
npm install -g asciicast2gif
```

## Recording the Demo

### Method 1: Using the Demo Script

The included `demo_script.sh` provides a scripted demo:

```bash
# Make the script executable
chmod +x demo_script.sh

# Record the demo
asciinema rec demo.cast -c "./demo_script.sh"
```

### Method 2: Manual Recording

For a more interactive demo:

```bash
# Start recording
asciinema rec demo.cast

# Run commands interactively
ollama-arena benchmark llama3.2:3b,qwen2.5-coder:7b --compare
ollama-arena genome scan
ollama-arena genome auto-seed --min-confidence 0.5
ollama-arena genome tree
ollama-arena leaderboard

# Stop recording with Ctrl+D
```

### Recording Tips

1. **Terminal Size**: Use a standard size (80x24 or 120x36) for consistency
   ```bash
   export COLUMNS=120 LINES=36
   ```

2. **Font**: Use a monospaced font with good rendering
   - Recommended: Source Code Pro, Fira Code, or JetBrains Mono
   - Size: 14-16pt

3. **Colors**: Ensure your terminal supports 256 colors for Rich library output

4. **Timing**: Add natural pauses between commands with `sleep 1` or `sleep 2`

## Converting to GIF

### Using agg (Recommended)

```bash
# Install agg
pip install agg

# Convert cast to GIF
agg demo.cast demo.gif

# Customize timing (default is 2x speed)
agg demo.cast demo.gif --fps 30 --font-size 14
```

### Using asciicast2gif

```bash
# Install
npm install -g asciicast2gif

# Convert
asciicast2gif demo.cast demo.gif
```

### Optimizing GIF Size

```bash
# Using gifsicle to optimize
brew install gifsicle  # macOS
sudo apt install gifsicle  # Linux

# Optimize
gifsicle -O3 demo.gif -o demo_optimized.gif
```

## Embedding in README

Add the GIF to your README.md:

```markdown
## Demo

![ollama-arena demo](demo.gif)
```

Or embed asciinema player for interactive viewing:

```markdown
## Demo

<script src="https://asciinema.org/a/XXXXXX.js" id="asciicast-XXXXXX" async></script>
```

## Alternative: Record with Terminalizer

Terminalizer is another option for recording terminal sessions:

```bash
# Install
npm install -g terminalizer

# Record
terminalizer record demo

# Export as GIF
terminalizer render demo -o demo.gif
```

## Best Practices

1. **Keep it short**: Aim for 30-60 seconds total
2. **Focus on features**: Show 3-5 key features maximum
3. **Clear commands**: Use descriptive command output
4. **Consistent styling**: Use the same terminal theme throughout
5. **Test playback**: Watch the recording to ensure it's smooth

## Suggested Demo Sequence

For ollama-arena v2.5.0, highlight these features:

1. Quick model comparison (`benchmark --compare`)
2. Genome lineage scanning (`genome scan`)
3. Automatic lineage inference (`genome auto-seed`)
4. Lineage tree visualization (`genome tree`)
5. ELO leaderboard (`leaderboard`)

Each feature should take ~10-15 seconds to demonstrate.
