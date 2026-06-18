# Demo Recording Guide for Ollama Arena

## Prerequisites
```bash
# Install asciinema
brew install asciinema  # macOS
# Or: sudo apt install asciinema  # Linux

# Install terminal recorder with timing support
pip install asciinema-automation
```

## Script for Demo Recording
Create a file `demo_script.sh`:

```bash
#!/bin/bash
# Ollama Arena Demo Script

# Clear terminal
clear

# Show banner
echo "=== Ollama Arena v2.5.0 Demo ==="
echo ""
sleep 2

# Check installation
echo "Checking installation..."
ollama-arena --help
sleep 3

# List available models
echo ""
echo "Available models:"
ollama-arena list
sleep 3

# Run quick benchmark
echo ""
echo "Running quick benchmark with 2 models..."
ollama-arena benchmark --models llama3:8b,mistral:7b --compare
sleep 5

# Show leaderboard
echo ""
echo "Current leaderboard:"
ollama-arena leaderboard
sleep 3

# Run battle royale
echo ""
echo "Starting 3-way battle royale..."
ollama-arena royale --models llama3:8b,mistral:7b,gemma:7b --category coding -n 3 --verbose
sleep 8

# Show results
echo ""
echo "Battle results:"
ollama-arena results --last 5
sleep 3

# Show genome evolution
echo ""
echo "Model genome evolution:"
ollama-arena genome tree --model llama3:8b
sleep 4

# Start web UI
echo ""
echo "Starting web interface..."
echo "Visit http://localhost:8000 to see the UI"
sleep 2

echo ""
echo "Demo complete! Thank you for watching."
```

## Recording Commands

### Basic Recording
```bash
# Start recording
asciinema rec ollama-arena-demo.cast

# Run your demo script
bash demo_script.sh

# Stop recording (Ctrl+D or exit)
```

### Advanced Recording with Timing
```bash
# Record with specific timing
asciinema rec -c "bash demo_script.sh" ollama-arena-demo.cast

# Record with idle time limit (to cut pauses)
asciinema rec -i 2 ollama-arena-demo.cast
```

### Post-Processing
```bash
# Trim recording
asciinema edit ollama-arena-demo.cast -o ollama-arena-trimmed.cast

# Upload to asciinema.org
asciinema upload ollama-arena-demo.cast

# Convert to GIF (requires additional tools)
asciinema gif ollama-arena-demo.cast -o demo.gif
```

## Demo Scenarios

### Scenario 1: Quick Start (2 minutes)
```bash
1. Installation check
2. List available models
3. Quick benchmark comparison
4. Show leaderboard
```

### Scenario 2: Advanced Features (5 minutes)
```bash
1. Installation check
2. Battle royale with 3 models
3. Multi-agent council debate
4. Genome evolution visualization
5. Web UI demonstration
```

### Scenario 3: MCP Tools Demo (3 minutes)
```bash
1. Show MCP tool registry
2. Enable web search tools
3. Run match with tools enabled
4. Show tool usage statistics
```

## Tips for Great Demos

1. **Terminal Size**: Use a standard terminal size (80x24 or 120x36)
2. **Font**: Use a monospaced font for clarity
3. **Speed**: Add appropriate sleep commands between actions
4. **Clarity**: Use clear, concise commands
5. **Error Handling**: Have backup commands in case of failures
6. **Preparation**: Ensure all required models are downloaded beforehand

## Automated Demo Script

Create `demo_automation.py`:

```python
#!/usr/bin/env python3
"""
Automated demo recording for Ollama Arena
"""
import subprocess
import time
import os

def run_command(cmd, wait=2):
    """Run a command with timing"""
    print(f"\n$ {cmd}")
    time.sleep(wait)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    time.sleep(wait)

def main():
    # Clear screen
    os.system('clear')
    
    # Demo sequence
    run_command("echo '=== Ollama Arena v2.5.0 Demo ==='")
    run_command("ollama-arena --help")
    run_command("ollama-arena list")
    run_command("ollama-arena leaderboard")
    run_command("ollama-arena benchmark --models llama3:8b,mistral:7b --compare", wait=5)
    run_command("ollama-arena results --last 3")
    
    print("\n=== Demo Complete ===")

if __name__ == "__main__":
    main()
```

## Recording with Automation
```bash
# Start asciinema recording
asciinema rec demo.cast -c "python3 demo_automation.py"

# Or use asciinema-automation for more control
pip install asciinema-automation
asciinema-automation record demo_script.yml demo.cast
```

## Embedding in README
Add to your README.md:

```markdown
## Demo

[![asciicast](https://asciinema.org/a/your-demo-id.svg)](https://asciinema.org/a/your-demo-id)
```

## Troubleshooting

### Recording Too Fast
- Add more `sleep` commands
- Use `-i` flag with asciinema to limit idle time

### Terminal Size Issues
- Set terminal size before recording: `resize -s 36 120`
- Use fixed terminal dimensions in asciinema config

### Model Download Issues
- Pre-download models: `ollama pull llama3:8b`
- Use smaller models for demo speed
- Add error handling in demo script