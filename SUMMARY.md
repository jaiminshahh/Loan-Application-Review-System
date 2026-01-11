# Loan Application Review System - Executive Summary

## Overview

The Loan Application Review System is an intelligent loan evaluation platform that combines the power of Large Language Models (LLMs) with deterministic verification to provide reliable, auditable loan decisions. The system analyzes 16 key financial factors across 6 categories to make data-driven lending decisions.

## Key Features

- **LLM Ensemble Architecture**: Uses 3 specialized LLM models running in parallel for comprehensive evaluation
- **Deterministic Verification**: All LLM outputs are validated against predefined thresholds
- **Comprehensive Evaluation**: Analyzes 16 factors including credit profile, income, debt, assets, and documentation
- **Risk-Weighted Scoring**: Incorporates risk scores and confidence levels into final decisions
- **Auditable Results**: Every decision includes source tracking, confidence scores, and detailed explanations
- **Professional Reporting**: Generates both Excel and JSON reports with color-coded results

## System Architecture

The system operates through a 5-layer pipeline:

```
Layer 1: Data Extractor     → Extracts clean data from Excel (Pure Python)
Layer 2: LLM Ensemble        → 3 specialized models evaluate factors (AI-powered)
Layer 3: Aggregator          → Calculates scores and metrics (Pure Python)
Layer 4: Decision Engine     → Applies business rules (Pure Python)
Layer 5: Output Generator    → Creates Excel/JSON reports (Pure Python)
```

### Layer Details

**Layer 1 - Data Extraction**
- Reads loan application data from Excel files
- Extracts and validates all required fields
- Ensures clean, typed data for downstream processing

**Layer 2 - LLM Ensemble Evaluation**
- **Factor Analyzer** (qwen2.5:7b): Math-focused numeric analysis
- **Risk Synthesizer** (llama3.1:8b): Pattern recognition and reasoning
- **Decision Maker** (mistral:7b): Decision-making and recommendations
- All models run in parallel for speed
- Outputs include decision, risk score (0-100), confidence (0-1), and notes

**Layer 3 - Aggregation**
- Collects ensemble results with majority voting
- Calculates weighted scores based on factor importance
- Computes average risk scores and confidence levels
- Identifies strengths and concerns by category

**Layer 4 - Decision Engine**
- Applies veto rules (any FAIL → REJECTED)
- Enforces confidence escalation thresholds
- Uses risk score thresholds (30/70) for automated decisions
- Generates detailed recommendations

**Layer 5 - Output Generation**
- Creates formatted Excel decision tables
- Generates machine-readable JSON reports
- Includes applicant details, evaluation results, and final decision

## Evaluation Factors

The system evaluates 16 factors across 6 categories:

### 1. Credit Profile
- Credit Score
- Payment History
- Credit Utilization
- Hard Inquiries (24 months)

### 2. Income & Employment
- Employment Status
- Employment Duration
- Gross Annual Income

### 3. Debt & Obligations
- Debt-to-Income Ratio
- Existing Loan Count

### 4. Assets & Collateral
- Liquid Assets / Loan Amount Ratio
- Collateral Offered

### 5. Banking & Relationship
- Bank Relationship
- NSF/Overdrafts (12 months)
- Monthly Cash Flow

### 6. Documentation
- Document Verification %
- Identity Verification

## Decision Rules

The system follows a strict rule hierarchy:

1. **Veto Rule** (Highest Priority): Any FAIL status → REJECTED
2. **Confidence Escalation**: Average confidence < 0.7 → MANUAL_REVIEW
3. **Risk Score Thresholds**:
   - Average risk < 30 → APPROVED
   - Average risk > 70 → REJECTED
   - Otherwise → MANUAL_REVIEW
4. **Score Thresholds** (Fallback):
   - Weighted score ≥ 80% → APPROVED
   - Weighted score < 60% → REJECTED
   - Otherwise → MANUAL_REVIEW

## How It Works

1. **Input**: Excel file with loan application data
2. **Processing**: 
   - Data extracted and validated
   - 16 factors evaluated by LLM ensemble
   - Results aggregated with risk weighting
   - Business rules applied for final decision
3. **Output**: 
   - Excel decision table with color-coded results
   - JSON report with complete evaluation data
   - Final decision: APPROVED, MANUAL_REVIEW, or REJECTED

## Usage

```bash
# Basic usage
python main.py --input data/loan_application.xlsx

# Sequential evaluation (for debugging)
python main.py --input data/loan_application.xlsx --sequential

# Custom output directory
python main.py --input data/loan_application.xlsx --output-dir reports
```

## Output Examples

**Console Output**: Rich, color-coded progress display showing:
- Extracted applicant data
- Evaluation progress across 16 factors
- Pass/Review/Fail counts with metrics
- Final decision with reasoning
- File paths for generated reports

**Excel Report**: Professional decision table with:
- Applicant information summary
- Factor-by-factor evaluation results
- Color-coded status indicators (Green/Yellow/Red)
- Risk scores and confidence levels
- Final decision and recommendations

**JSON Report**: Machine-readable output containing:
- Complete applicant data
- Detailed evaluation results
- Aggregated metrics
- Final decision with rule applied

## Technical Requirements

- Python 3.8+
- Ollama with 3 LLM models:
  - qwen2.5:7b (math-focused)
  - llama3.1:8b (reasoning)
  - mistral:7b (decision-making)
- Dependencies: pandas, openpyxl, langchain-ollama, rich

## Benefits

- **Reliable**: Deterministic verification prevents LLM errors
- **Fast**: Parallel ensemble processing + instant Python layers
- **Debuggable**: Each layer independently testable
- **Accurate**: Structured outputs with confidence scoring
- **Explainable**: Complete audit trail for every decision
- **Specialized**: Role-optimized models for better results

## System Metrics

When processing applications, the system tracks:
- **Weighted Score**: Overall application strength (0-100%)
- **Average Risk Score**: Combined risk assessment (0-100)
- **Average Confidence**: Model certainty in evaluations (0-1)
- **Pass/Review/Fail Counts**: Status distribution across factors
- **Risk Level**: LOW, MODERATE, HIGH, or VERY_HIGH

## Conclusion

The Loan Application Review System provides a robust, transparent, and efficient approach to loan evaluation by combining AI-powered analysis with deterministic safeguards. It offers financial institutions a reliable tool for making consistent, well-documented lending decisions while maintaining human oversight through manual review escalation.
