# Fish completion script for ollama-arena

complete -c ollama-arena -f

# Main commands
complete -c ollama-arena -n "__fish_use_subcommand" -a benchmark -d "Standardized 30-task Score"
complete -c ollama-arena -n "__fish_use_subcommand" -a match -d "Head-to-head battle(s)"
complete -c ollama-arena -n "__fish_use_subcommand" -a tournament -d "Round-robin tournament"
complete -c ollama-arena -n "__fish_use_subcommand" -a royale -d "N-way simultaneous battle royale"
complete -c ollama-arena -n "__fish_use_subcommand" -a council -d "Multi-agent debate"
complete -c ollama-arena -n "__fish_use_subcommand" -a resolve-issue -d "Run autonomous agent to resolve an issue"
complete -c ollama-arena -n "__fish_use_subcommand" -a optimize-prompt -d "Auto-optimize a model's system prompt"
complete -c ollama-arena -n "__fish_use_subcommand" -a review-pr -d "Review current git diff using models"
complete -c ollama-arena -n "__fish_use_subcommand" -a import -d "Import a local CSV/JSON dataset"
complete -c ollama-arena -n "__fish_use_subcommand" -a export -d "Export data to CSV/JSON"
complete -c ollama-arena -n "__fish_use_subcommand" -a leaderboard -d "Show ELO rankings"
complete -c ollama-arena -n "__fish_use_subcommand" -a anti-leaderboard -d "Show hallucination rankings"
complete -c ollama-arena -n "__fish_use_subcommand" -a list -d "List models available on the backend"
complete -c ollama-arena -n "__fish_use_subcommand" -a tasks -d "List built-in task categories and counts"
complete -c ollama-arena -n "__fish_use_subcommand" -a results -d "Browse match history and per-task details"
complete -c ollama-arena -n "__fish_use_subcommand" -a inspect -d "Show every recorded run for a single task ID"
complete -c ollama-arena -n "__fish_use_subcommand" -a report -d "Per-model category breakdown"
complete -c ollama-arena -n "__fish_use_subcommand" -a datasets -d "HF dataset cache"
complete -c ollama-arena -n "__fish_use_subcommand" -a finetune -d "Unsloth pipeline"
complete -c ollama-arena -n "__fish_use_subcommand" -a genome -d "Model genome and evolution tracking"
complete -c ollama-arena -n "__fish_use_subcommand" -a mcp -d "MCP tools management"
complete -c ollama-arena -n "__fish_use_subcommand" -a web -d "Web UI server"

# Options for match/tournament/royale
complete -c ollama-arena -n "__fish_seen_subcommand_from match tournament royale" -l category -d "Task category" -x -a "coding reasoning security planning inspection math knowledge creative json_format tool_use vision all"
complete -c ollama-arena -n "__fish_seen_subcommand_from match tournament royale" -l difficulty -d "Task difficulty" -x -a "easy medium hard"
complete -c ollama-arena -n "__fish_seen_subcommand_from match tournament royale" -l models -d "Models to use" -x
complete -c ollama-arena -n "__fish_seen_subcommand_from match tournament royale" -l backend -d "Backend type" -x -a "vllm lmstudio llamacpp openai groq together openrouter"
complete -c ollama-arena -n "__fish_seen_subcommand_from match tournament royale" -l tools -d "Enable tool use"
complete -c ollama-arena -n "__fish_seen_subcommand_from match tournament royale" -l verbose -d "Verbose output"

# MCP commands
complete -c ollama-arena -n "__fish_seen_subcommand_from mcp" -a list -d "List MCP tools"
complete -c ollama-arena -n "__fish_seen_subcommand_from mcp" -a enable -d "Enable MCP tool"
complete -c ollama-arena -n "__fish_seen_subcommand_from mcp" -a disable -d "Disable MCP tool"
complete -c ollama-arena -n "__fish_seen_subcommand_from mcp" -a install -d "Install MCP server"
complete -c ollama-arena -n "__fish_seen_subcommand_from mcp" -a diagnose -d "Diagnose MCP issues"

# Global options
complete -c ollama-arena -l ollama -d "Ollama server URL"
complete -c ollama-arena -l backend -d "Backend URL or preset"
complete -c ollama-arena -l api-key -d "API key"
complete -c ollama-arena -l db -d "Database path"