# Benchmarks & ELO

## ELO Rating System

`ollama-arena` uses the standard chess ELO rating algorithm to measure relative model capabilities. 

### K-Factor and Updates

* The default K-factor is set to **`K = 32`**.
* Unlike standard tournament settings that update ratings at the end of a match, `ollama-arena` updates ELO ratings **after every single task**. This accelerates convergence but can cause slight noise over small sample sizes.
* ELO values start at a default base rating of **1200**.

### ELO Formulas

For two models with ratings $R_A$ and $R_B$:

**Expected Outcome:**
$$E_A = \frac{1}{1 + 10^{(R_B - R_A) / 400}}$$
$$E_B = \frac{1}{1 + 10^{(R_A - R_B) / 400}}$$

**Rating Update:**
$$R'_A = R_A + K \times (S_A - E_A)$$
$$R'_B = R_B + K \times (S_B - E_B)$$

Where $S_A$ is the score of Model A (1.0 for a win, 0.5 for a draw, 0.0 for a loss).

---

## Evaluation Categories

Evaluations are auto-scored using distinct routers and scripts inside `evaluator.py`:

1. **Coding**: Runs generated code alongside validation assertions in a sandboxed Python environment (or language-specific interpreters for JS/TS/Go/Rust/C++).
2. **Reasoning / Math / Knowledge**: Performs string pattern matching (exact, substring, prefix, contains_all, contains_any, numeric approximation with tolerances).
3. **Security**: Inspects responses for presence of expected vulnerability signatures and security considerations.
4. **Planning / Inspection**: Inspects generated structural/logical steps against predefined key elements and checklists.
5. **Creative**: Open-ended prompts. Scored `0.5` by default unless `use_judge=True` is enabled, which routes evaluation to a designated LLM Judge (e.g. GPT-4).
