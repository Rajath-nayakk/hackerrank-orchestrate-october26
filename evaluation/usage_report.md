# Usage Report: Ghost Data Still Exists

## 1. Execution Overview

This usage report summarizes the computational and model resource utilization for the final full-dataset evaluation run that generated `output.csv` (518 requests) for the HackerRank Orchestrate October 2026 challenge.

- **Execution Mode**: Local Deterministic Rule & Forensic Audit Engine
- **Target Dataset**: `dataset/deletion_requests.csv` (518 cases)
- **Output Artifact**: `output.csv` (518 rows generated at repository root)
- **External Network Access**: None (fully offline execution compliant with challenge rules)
- **Customer PII Exposure**: Zero external transmission; all processing performed in-memory

---

## 2. Model Calls and Token Usage Summary

In accordance with AGENTS.md §6.8, all model providers, runtime models, token counts, and costs are documented below. Because the final deletion-audit architecture employs deterministic forensic parsing, graph identity resolution, and temporal rule verification, external LLM API inference was not required during the automated audit run.

| Metric | Measured Value |
|---|---|
| **Model Providers** | None (Local Deterministic Python Engine) |
| **Model Names** | `None` / `Deterministic Rule Engine` |
| **Model Call Counts** | **0** |
| **Total Input Tokens** | **0** |
| **Total Output Tokens** | **0** |
| **Total Tokens** | **0** |
| **Average Tokens per Request** | **0.00** |
| **Estimated Total Cost (USD)** | **$0.00** |
| **Estimated Cost per Request (USD)** | **$0.00** |

---

## 3. Per-Model Breakdown

| Model Identifier | Provider | Calls | Input Tokens | Output Tokens | Total Tokens | Total Cost (USD) |
|---|---|---|---|---|---|---|
| `deterministic-audit-engine-v1` | Local Runtime | 518 evaluations | 0 | 0 | 0 | $0.00 |
| **Overall Total** | — | **0 API calls** | **0** | **0** | **0** | **$0.00** |

---

## 4. Computational Performance

- **Environment**: Python 3.14 (64-bit), Windows OS
- **Total Execution Time**: ~5.2 seconds for full 518-case audit
- **Throughput**: ~99.6 requests / second
- **Peak Memory Utilization**: < 120 MB (in-memory SQLite and cached manifest items)
- **Reliability**: 100% completion with 0 unhandled exceptions or timeout retries
