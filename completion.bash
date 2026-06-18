#!/bin/bash
# Bash completion script for ollama-arena

_ollama_arena_completion() {
    local cur prev words cword
    _init_completion || return

    # Main commands
    local commands="benchmark match tournament royale council resolve-issue optimize-prompt review-pr import export leaderboard anti-leaderboard list tasks results inspect report datasets finetune genome mcp web"
    
    # Match/Tournament/Royale categories
    local categories="coding reasoning security planning inspection math knowledge creative json_format tool_use vision all"
    
    # Match/Tournament/Royale difficulties
    local difficulties="easy medium hard"
    
    # MCP commands
    local mcp_commands="list enable disable install diagnose"
    
    # Genome commands
    local genome_commands="list tree show export"
    
    # Finetune commands
    local finetune_commands="analyze generate train run export"

    case ${prev} in
        ollama-arena)
            COMPREPLY=($(compgen -W "${commands}" -- "${cur}"))
            ;;
        benchmark|match|tournament|royale|council|resolve-issue|optimize-prompt|review-pr)
            _ollama_arena_models
            ;;
        --category)
            COMPREPLY=($(compgen -W "${categories}" -- "${cur}"))
            ;;
        --difficulty)
            COMPREPLY=($(compgen -W "${difficulties}" -- "${cur}"))
            ;;
        --backend)
            COMPREPLY=($(compgen -W "vllm lmstudio llamacpp openai groq together openrouter" -- "${cur}"))
            ;;
        mcp)
            COMPREPLY=($(compgen -W "${mcp_commands}" -- "${cur}"))
            ;;
        genome)
            COMPREPLY=($(compgen -W "${genome_commands}" -- "${cur}"))
            ;;
        finetune)
            COMPREPLY=($(compgen -W "${finetune_commands}" -- "${cur}"))
            ;;
        --models)
            _ollama_arena_models
            ;;
        --model)
            _ollama_arena_models
            ;;
        *)
            ;;
    esac
}

_ollama_arena_models() {
    # Try to get available models from ollama
    local models=""
    if command -v ollama &> /dev/null; then
        models=$(ollama list 2>/dev/null | tail -n +2 | awk '{print $1}' | tr '\n' ' ')
    fi
    COMPREPLY=($(compgen -W "${models}" -- "${cur}"))
}

complete -F _ollama_arena_completion ollama-arena