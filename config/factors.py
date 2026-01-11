"""
Factor Definitions and Thresholds

All the factors we evaluate, their weights, and the criteria for PASS/REVIEW/FAIL.
"""
from dataclasses import dataclass
from typing import Callable, Any
from enum import Enum


class Status(str, Enum):
    PASS = "PASS"
    REVIEW = "REVIEW"
    FAIL = "FAIL"


@dataclass
class Factor:
    """Definition of a single evaluation factor."""
    id: str
    name: str
    category: str
    weight: float
    criteria_text: str
    # Thresholds for automatic evaluation (used if LLM fails)
    pass_threshold: Any = None
    fail_threshold: Any = None
    comparison: str = "gte"  # gte, lte, eq, in


# All factors grouped by category
FACTORS = {
    # === CREDIT FACTORS ===
    "credit_score": Factor(
        id="credit_score",
        name="Credit Score",
        category="Credit Profile",
        weight=0.20,
        criteria_text="≥700: Pass | 650-699: Review | <650: Fail",
        pass_threshold=700,
        fail_threshold=650,
        comparison="gte"
    ),
    "payment_history": Factor(
        id="payment_history",
        name="Payment History",
        category="Credit Profile",
        weight=0.10,
        criteria_text="≥98%: Pass | 95-97.9%: Review | <95%: Fail",
        pass_threshold=98.0,
        fail_threshold=95.0,
        comparison="gte"
    ),
    "credit_utilization": Factor(
        id="credit_utilization",
        name="Credit Utilization",
        category="Credit Profile",
        weight=0.05,
        criteria_text="≤30%: Pass | 31-50%: Review | >50%: Fail",
        pass_threshold=30.0,
        fail_threshold=50.0,
        comparison="lte"
    ),
    "hard_inquiries": Factor(
        id="hard_inquiries",
        name="Hard Inquiries (24mo)",
        category="Credit Profile",
        weight=0.03,
        criteria_text="0-2: Pass | 3-5: Review | >5: Fail",
        pass_threshold=2,
        fail_threshold=5,
        comparison="lte"
    ),
    
    # === INCOME FACTORS ===
    "employment_status": Factor(
        id="employment_status",
        name="Employment Status",
        category="Income & Employment",
        weight=0.10,
        criteria_text="Full-Time: Pass | Part-Time/Contract: Review | Unemployed: Fail",
        pass_threshold=["Full-Time", "Full-Time Employed"],
        fail_threshold=["Unemployed", "None"],
        comparison="in"
    ),
    "employment_duration": Factor(
        id="employment_duration",
        name="Employment Duration",
        category="Income & Employment",
        weight=0.05,
        criteria_text="≥2 years: Pass | 1-2 years: Review | <1 year: Fail",
        pass_threshold=2.0,
        fail_threshold=1.0,
        comparison="gte"
    ),
    "annual_income": Factor(
        id="annual_income",
        name="Gross Annual Income",
        category="Income & Employment",
        weight=0.15,
        criteria_text="≥$50K: Pass | $30-50K: Review | <$30K: Fail",
        pass_threshold=50000,
        fail_threshold=30000,
        comparison="gte"
    ),
    
    # === DEBT FACTORS ===
    "dti_ratio": Factor(
        id="dti_ratio",
        name="Debt-to-Income Ratio",
        category="Debt & Obligations",
        weight=0.15,
        criteria_text="≤36%: Pass | 37-43%: Review | >43%: Fail",
        pass_threshold=36.0,
        fail_threshold=43.0,
        comparison="lte"
    ),
    "existing_loans": Factor(
        id="existing_loans",
        name="Existing Loan Count",
        category="Debt & Obligations",
        weight=0.03,
        criteria_text="0-2: Pass | 3-4: Review | >4: Fail",
        pass_threshold=2,
        fail_threshold=4,
        comparison="lte"
    ),
    
    # === ASSET FACTORS ===
    "liquid_assets_ratio": Factor(
        id="liquid_assets_ratio",
        name="Liquid Assets / Loan Amount",
        category="Assets & Collateral",
        weight=0.05,
        criteria_text="≥100%: Pass | 50-99%: Review | <50%: Fail",
        pass_threshold=100.0,
        fail_threshold=50.0,
        comparison="gte"
    ),
    "collateral_offered": Factor(
        id="collateral_offered",
        name="Collateral Offered",
        category="Assets & Collateral",
        weight=0.02,
        criteria_text="Adequate: Pass | Partial/None: Review",
        pass_threshold=["Yes", "Adequate", "Full"],
        fail_threshold=[],  # No collateral doesn't fail
        comparison="in"
    ),
    
    # === BANKING FACTORS ===
    "bank_relationship": Factor(
        id="bank_relationship",
        name="Bank Relationship",
        category="Banking & Relationship",
        weight=0.03,
        criteria_text="≥3 years: Pass | 1-3 years: Review | <1 year: Fail",
        pass_threshold=3.0,
        fail_threshold=1.0,
        comparison="gte"
    ),
    "nsf_count": Factor(
        id="nsf_count",
        name="NSF/Overdrafts (12mo)",
        category="Banking & Relationship",
        weight=0.02,
        criteria_text="0: Pass | 1-2: Review | >2: Fail",
        pass_threshold=0,
        fail_threshold=2,
        comparison="lte"
    ),
    "monthly_cash_flow": Factor(
        id="monthly_cash_flow",
        name="Monthly Cash Flow",
        category="Banking & Relationship",
        weight=0.02,
        criteria_text="Positive: Pass | Zero: Review | Negative: Fail",
        pass_threshold=0,
        fail_threshold=0,
        comparison="gte"
    ),
    
    # === DOCUMENT FACTORS ===
    "docs_verified_pct": Factor(
        id="docs_verified_pct",
        name="Document Verification %",
        category="Documentation",
        weight=0.03,
        criteria_text="100%: Pass | 90-99%: Review | <90%: Fail",
        pass_threshold=100.0,
        fail_threshold=90.0,
        comparison="gte"
    ),
    "identity_verified": Factor(
        id="identity_verified",
        name="Identity Verification",
        category="Documentation",
        weight=0.02,
        criteria_text="Full: Pass | Partial: Review | Failed: Fail",
        pass_threshold=[True, "Full", "Verified", "Yes"],
        fail_threshold=[False, "Failed", "No"],
        comparison="in"
    ),
}


def evaluate_with_threshold(factor_id: str, value: Any) -> Status:
    """
    Evaluate a factor using predefined thresholds.
    This is the fallback if LLM evaluation fails.
    """
    factor = FACTORS.get(factor_id)
    if not factor:
        return Status.REVIEW
    
    try:
        if factor.comparison == "gte":
            if value >= factor.pass_threshold:
                return Status.PASS
            elif value < factor.fail_threshold:
                return Status.FAIL
            else:
                return Status.REVIEW
                
        elif factor.comparison == "lte":
            if value <= factor.pass_threshold:
                return Status.PASS
            elif value > factor.fail_threshold:
                return Status.FAIL
            else:
                return Status.REVIEW
                
        elif factor.comparison == "in":
            if any(str(value).lower() == str(v).lower() for v in (factor.pass_threshold or [])):
                return Status.PASS
            elif any(str(value).lower() == str(v).lower() for v in (factor.fail_threshold or [])):
                return Status.FAIL
            else:
                return Status.REVIEW
                
    except (TypeError, ValueError):
        return Status.REVIEW
    
    return Status.REVIEW


# Business Rules for final decision
DECISION_RULES = [
    {"id": "R01", "condition": "all_pass", "decision": "APPROVED", "description": "All factors passed"},
    {"id": "R02", "condition": "any_fail", "decision": "REJECTED", "description": "One or more factors failed"},
    {"id": "R03", "condition": "score_gte_80", "decision": "APPROVED", "description": "No failures, score ≥80%"},
    {"id": "R04", "condition": "score_gte_60", "decision": "MANUAL_REVIEW", "description": "No failures, score 60-79%"},
    {"id": "R05", "condition": "score_lt_60", "decision": "REJECTED", "description": "No failures, score <60%"},
]
