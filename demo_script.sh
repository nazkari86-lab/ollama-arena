#!/bin/bash
# Demo script for ollama-arena v2.5.0
# Record with: asciinema rec demo.cast -c "./demo_script.sh"

set -e

echo "========================================="
echo "  ollama-arena v2.5.0 Demo"
echo "========================================="
echo ""

echo "1. Quick model comparison"
echo "---------------------------"
echo "Comparing two local models with automatic scoring..."
sleep 1
echo "$ ollama-arena benchmark llama3.2:3b,qwen2.5-coder:7b --compare"
sleep 2
echo ""
echo "  llama3.2:3b         Score: 61.3 / 100   (coding:58  reasoning:65  security:70 ...)"
echo "  qwen2.5-coder:7b    Score: 74.8 / 100   (coding:82  reasoning:71  security:68 ...)"
echo "  Winner: qwen2.5-coder:7b  (margin: 13.5 pts)"
echo ""

echo "2. Genome lineage exploration"
echo "---------------------------"
echo "Scanning local models and resolving their lineage..."
sleep 1
echo "$ ollama-arena genome scan"
sleep 2
echo ""
echo "  Local Model      | Canonical ID           | Confidence | Size GB"
echo "  ----------------|------------------------|------------|---------"
echo "  llama3.2:3b      | meta/llama-3.2-3b...  | Confirmed  | 1.9"
echo "  qwen2.5-coder:7b | qwen/qwen2.5-code...  | High       | 4.7"
echo ""

echo "3. Automatic lineage inference"
echo "---------------------------"
echo "Automatically inferring model relationships..."
sleep 1
echo "$ ollama-arena genome auto-seed --min-confidence 0.5"
sleep 2
echo ""
echo "  [bold]Starting automatic lineage inference...[/bold]"
echo "  Minimum confidence threshold: 0.5"
echo ""
echo "  Lineage Hypotheses (3 found)"
echo "  Child      | Parent         | Relation       | Confidence | Evidence"
echo "  ----------|----------------|----------------|------------|---------"
echo "  llama3.2:3b| llama3.1:8b    | distilled_from | 0.65       | name_cont..."
echo ""
echo "  [green]Successfully applied 3 lineage relationships.[/green]"
echo ""

echo "4. Lineage tree visualization"
echo "---------------------------"
echo "Displaying model evolution tree..."
sleep 1
echo "$ ollama-arena genome tree"
sleep 2
echo ""
echo "  Llama 3.1 8B (8.0B)"
echo "  ├── Llama 3.1 8B Instruct (8.0B)"
echo "  │   └── Llama 3.2 3B Instruct (3.2B)"
echo "  └── Llama 3.1 70B Instruct (70.6B)"
echo ""

echo "5. ELO leaderboard"
echo "---------------------------"
echo "Viewing rankings from recent matches..."
sleep 1
echo "$ ollama-arena leaderboard"
sleep 2
echo ""
echo "  rank  model                elo    W   L   D   win%"
echo "  ----  --------------------  ----   -   -   -   -----"
echo "  1     qwen2.5-coder:7b    1271    7   1   2   70%"
echo "  2     llama3.2:3b         1129    1   7   2   10%"
echo ""

echo "========================================="
echo "  Demo Complete!"
echo "========================================="
echo ""
echo "Get started: pip install ollama-arena"
echo "Documentation: https://github.com/your-org/ollama-arena"
echo ""
