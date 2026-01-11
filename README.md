# Loan Decision System v2 - LLM Ensemble Architecture

A robust loan evaluation system using a specialized LLM ensemble with deterministic verification for reliable, auditable results.

## Architecture

```
Excel Input
     │
     ▼
┌─────────────────────────────────┐
│  LAYER 1: Data Extractor        │  ← Pure Python
│  (Extracts clean typed values)  │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  LAYER 2: LLM Ensemble          │  ← Multi-model LLM (Parallel)
│  (3 specialized roles, verified)│
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  LAYER 3: Aggregator            │  ← Pure Python
│  (Counts, calculates scores)    │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  LAYER 4: Decision Engine       │  ← Pure Python
│  (Applies business rules)       │
└─────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────┐
│  LAYER 5: Output Generator      │  ← Pure Python
│  (Excel + JSON reports)         │
└─────────────────────────────────┘
```

## Project Structure

```
loan_decision_system_v2/
├── main.py                 # Orchestrator
├── requirements.txt
├── config/
│   ├── factors.py          # Factor definitions & thresholds
│   └── llm_config.py       # Ollama configuration
├── core/
│   ├── data_extractor.py   # Layer 1: Excel → Clean JSON
│   ├── evaluators.py       # Layer 2: Micro-agent evaluations
│   ├── aggregator.py       # Layer 3: Collect & score
│   └── decision_engine.py  # Layer 4: Business rules
├── output/
│   └── generator.py        # Layer 5: Excel/JSON output
└── data/
    └── sample_input.xlsx   # Sample data
```

## Setup

```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve

# 2. Pull required models (ensemble uses specialized models per role)
ollama pull qwen2.5:7b      # Math-focused: factor_analyzer role
ollama pull llama3.1:8b     # Reasoning: risk_synthesizer role
ollama pull mistral:7b      # Decision-making: decision_maker role

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python main.py --input data/pratik_loan_input_data.xlsx
```

**Note:** The system uses a specialized ensemble:
- **factor_analyzer**: `qwen2.5:7b` (optimized for numeric/math analysis)
- **risk_synthesizer**: `llama3.1:8b` (good at reasoning and pattern recognition)
- **decision_maker**: `mistral:7b` (strong at decision-making and recommendations)

Each role uses role-specific prompts tailored to its task.

## Why This Architecture?

| Layer | Uses LLM? | Reason |
|-------|-----------|--------|
| Data Extraction | ❌ | Deterministic - we know the Excel structure |
| Evaluation | ✅ | Multi-model ensemble with role-specific prompts |
| Verification | ❌ | Deterministic thresholds verify LLM outputs |
| Aggregation | ❌ | Just math - counting, averaging, risk-weighting |
| Decision | ❌ | Rules are clear (veto, confidence, risk thresholds) |
| Output | ❌ | Just formatting |

**Benefits:**
- **Reliable**: Deterministic verification catches LLM math errors and contradictions
- **Fast**: Python layers are instant, LLM ensemble runs in parallel
- **Debuggable**: Each layer can be tested independently; all decisions have source tracking
- **Accurate**: Structured JSON outputs with confidence scores; deterministic override when uncertain
- **Explainable**: Every decision shows source (ensemble/threshold), confidence, and disagreement flags
- **Specialized**: Different models and prompts per role (math-focused, reasoning-focused, decision-focused)
