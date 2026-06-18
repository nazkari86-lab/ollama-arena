# LLM Genome Explorer Architecture

## 1. Overview
The **LLM Genome Explorer** is a comprehensive analytical platform and knowledge graph designed to track the evolution, architecture, and lineage of Large Language Models (LLMs). It moves beyond black-box evaluation to provide a deep understanding of model "genetics."

## 2. Core Modules

### Module 1: Ollama Scanner
Source of local model data.
- **Commands:** `ollama list`, `ollama show`, `ollama show --modelfile`, `ollama show --parameters`
- **Extracted Data:** Name, Tag, Size, Quantization, Base Model (`FROM`), Template, System Prompts.

### Module 2: Genome Resolver
Maps local models to the canonical registry.
- **Pipeline:**
  1. **Parsing:** Normalizing `Modelfile` instructions.
  2. **Candidate Search:** Identifying potential matches (e.g., `Mistral 7B` vs `Mistral Instruct`).
  3. **Evidence Matching:** Passing candidates through the Evidence Engine.

### Module 3: Evidence Engine
The multi-source validation core.
- **Local Evidence:** Signals from the local environment.
- **Structural Evidence:** Hardware-level parameters (layers, heads, hidden size, context length, GQA, MoE).
- **Metadata Evidence:** Model cards, release notes, and research papers.
- **Fingerprint Evidence:** Optional artifact hashes or layer segment fingerprints.

### Module 4: Confidence Scorer
Assigns confidence levels to every claim.
- **Levels:** Confirmed, High, Medium, Low, Unknown, Conflict.

### Module 5: Genome Database (Genome DB)
The canonical source of truth.
- **Entities:**
  - **Model:** ID, Name, Family, Org, Date, License.
  - **Architecture:** Layers, Embd size, Heads, GQA, MoE, Context, Tokenizer.
  - **Lineage:** Parent, Child, Merge, Distill, Fine-tune.
  - **Evidence:** Source URL, Timestamp, Confidence score.

### Module 6: Graph Engine
Represents lineage as a non-linear network.
- **Relation Types:** `trained_from`, `fine_tuned_from`, `merged_from`, `distilled_from`, `quantized_from`, `converted_from`.

### Module 7: Canonical Genome Network
A central repository managed by the project (Llama, Qwen, Gemma, Mistral, etc.).
- **Delivery:** via Genome API for local synchronization.

### Module 8: Local Overlay Database (`local_overlay.db`)
Protects privacy for proprietary or sensitive models.
- Stores local fine-tunes, internal notes, and private lineage.

### Module 9: Privacy Layer
- **Offline Mode:** No sync, no internet, completely local.
- **Enriched Mode:** Fetch metadata anonymously from the central API.
- **Contribute Mode:** Voluntarily share lineage and architecture to the community.

### Module 10: Genome Sync
Background process to update the local canonical knowledge base without transferring large model weights.

### Module 11: User Interface
- **Genome Tree:** Visual evolution visualization.
- **Architecture Card:** Technical specifications overview.
- **Comparison Engine:** Structural and lineage distance between models.
- **Evidence/Confidence Tabs:** Transparency on why a model was identified as a specific descendant.

### Module 12: Future Capabilities
- **Merge Advisor:** Compatibility checking for MergeKit (tokenizers, layers, architecture).
- **Evolution Timeline:** Historical map of LLM technology breakthroughs (RoPE, GQA, MoE).
- **Technology Explorer:** Tracking the spread of specific architectural innovations.

## 3. Philosophical Pillars
1. **Ollama** shows what you have.
2. **Genome Resolver** determines what it is.
3. **Evidence Engine** proves why we think so.
4. **Genome DB** stores the world's knowledge.
5. **Local Overlay** protects your private research.
6. **Genome Network** synchronizes global intelligence.
