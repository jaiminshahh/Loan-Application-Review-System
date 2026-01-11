"""
LAYER 4: Decision Engine

Pure Python - applies business rules to determine final decision.
Uses veto rules, confidence escalation, and thresholded avg_risk_score.
"""
from dataclasses import dataclass
from typing import List
from core.aggregator import AggregatedResults, get_risk_level


# Configuration
CONFIDENCE_ESCALATION_THRESHOLD = 0.7  # If avg_confidence < this, escalate to MANUAL_REVIEW
RISK_SCORE_APPROVE_THRESHOLD = 30.0  # If avg_risk_score < this, can approve
RISK_SCORE_REJECT_THRESHOLD = 70.0  # If avg_risk_score > this, reject


@dataclass
class FinalDecision:
    """Final loan decision."""
    decision: str  # APPROVED, MANUAL_REVIEW, REJECTED
    rule_applied: str
    rule_description: str
    weighted_score: float
    pass_count: int
    review_count: int
    fail_count: int
    risk_level: str
    recommendation: str
    average_risk_score: float = 50.0
    average_confidence: float = 0.5


def make_decision(
    results: AggregatedResults,
    confidence_threshold: float = CONFIDENCE_ESCALATION_THRESHOLD,
    risk_approve_threshold: float = RISK_SCORE_APPROVE_THRESHOLD,
    risk_reject_threshold: float = RISK_SCORE_REJECT_THRESHOLD
) -> FinalDecision:
    """
    Apply business rules with veto, confidence escalation, and risk_score thresholds.
    
    Rules (in priority order):
    1. Veto: Any FAIL -> REJECTED
    2. Confidence escalation: Low avg_confidence -> MANUAL_REVIEW
    3. Risk score thresholds: avg_risk_score < 30 -> APPROVE, >70 -> REJECT, else REVIEW
    4. Fallback to weighted_score thresholds
    
    Returns FinalDecision with all details.
    """
    
    # Rule 1: Veto - Any FAIL -> REJECTED (highest priority)
    if results.fail_count > 0:
        matched_rule = {
            "id": "R01",
            "description": "Veto: One or more factors failed",
            "decision": "REJECTED"
        }
        recommendation = _generate_recommendation("REJECTED", results, matched_rule["description"])
        return FinalDecision(
            decision="REJECTED",
            rule_applied="R01",
            rule_description=matched_rule["description"],
            weighted_score=results.weighted_score,
            pass_count=results.pass_count,
            review_count=results.review_count,
            fail_count=results.fail_count,
            risk_level=get_risk_level(results),
            recommendation=recommendation,
            average_risk_score=results.average_risk_score,
            average_confidence=results.average_confidence
        )
    
    # Rule 2: Confidence escalation - Low confidence -> MANUAL_REVIEW
    if results.average_confidence < confidence_threshold:
        matched_rule = {
            "id": "R02",
            "description": f"Confidence escalation: Low ensemble confidence ({results.average_confidence:.2f} < {confidence_threshold})",
            "decision": "MANUAL_REVIEW"
        }
        recommendation = _generate_recommendation("MANUAL_REVIEW", results, matched_rule["description"])
        return FinalDecision(
            decision="MANUAL_REVIEW",
            rule_applied="R02",
            rule_description=matched_rule["description"],
            weighted_score=results.weighted_score,
            pass_count=results.pass_count,
            review_count=results.review_count,
            fail_count=results.fail_count,
            risk_level=get_risk_level(results),
            recommendation=recommendation,
            average_risk_score=results.average_risk_score,
            average_confidence=results.average_confidence
        )
    
    # Rule 3: Risk score thresholds (no failures, confidence OK)
    if results.average_risk_score < risk_approve_threshold:
        matched_rule = {
            "id": "R03",
            "description": f"Low risk score: {results.average_risk_score:.1f} < {risk_approve_threshold}",
            "decision": "APPROVED"
        }
        recommendation = _generate_recommendation("APPROVED", results, matched_rule["description"])
        return FinalDecision(
            decision="APPROVED",
            rule_applied="R03",
            rule_description=matched_rule["description"],
            weighted_score=results.weighted_score,
            pass_count=results.pass_count,
            review_count=results.review_count,
            fail_count=results.fail_count,
            risk_level=get_risk_level(results),
            recommendation=recommendation,
            average_risk_score=results.average_risk_score,
            average_confidence=results.average_confidence
        )
    
    elif results.average_risk_score > risk_reject_threshold:
        matched_rule = {
            "id": "R04",
            "description": f"High risk score: {results.average_risk_score:.1f} > {risk_reject_threshold}",
            "decision": "REJECTED"
        }
        recommendation = _generate_recommendation("REJECTED", results, matched_rule["description"])
        return FinalDecision(
            decision="REJECTED",
            rule_applied="R04",
            rule_description=matched_rule["description"],
            weighted_score=results.weighted_score,
            pass_count=results.pass_count,
            review_count=results.review_count,
            fail_count=results.fail_count,
            risk_level=get_risk_level(results),
            recommendation=recommendation,
            average_risk_score=results.average_risk_score,
            average_confidence=results.average_confidence
        )
    
    # Rule 4: Fallback to weighted_score thresholds
    if results.weighted_score >= 80:
        matched_rule = {
            "id": "R05",
            "description": f"No failures, strong weighted score: {results.weighted_score}% ≥ 80%",
            "decision": "APPROVED"
        }
    elif results.weighted_score >= 60:
        matched_rule = {
            "id": "R06",
            "description": f"No failures, moderate weighted score: {results.weighted_score}% (60-79%)",
            "decision": "MANUAL_REVIEW"
        }
    else:
        matched_rule = {
            "id": "R07",
            "description": f"No failures, weak weighted score: {results.weighted_score}% < 60%",
            "decision": "REJECTED"
        }
    
    recommendation = _generate_recommendation(matched_rule["decision"], results, matched_rule["description"])
    return FinalDecision(
        decision=matched_rule["decision"],
        rule_applied=matched_rule["id"],
        rule_description=matched_rule["description"],
        weighted_score=results.weighted_score,
        pass_count=results.pass_count,
        review_count=results.review_count,
        fail_count=results.fail_count,
        risk_level=get_risk_level(results),
        recommendation=recommendation,
        average_risk_score=results.average_risk_score,
        average_confidence=results.average_confidence
    )


def _generate_recommendation(decision: str, results: AggregatedResults, rule_description: str) -> str:
    """Generate recommendation text based on decision and results."""
    
    if decision == "APPROVED":
        if results.review_count == 0:
            return f"Clean approval. All factors meet criteria. Risk score: {results.average_risk_score:.1f}, Confidence: {results.average_confidence:.2f}. Proceed with standard terms."
        else:
            concerns = [e.factor_name for e in results.evaluations 
                       if e.status.value == "REVIEW"][:3]
            return (f"Approve with monitoring. {results.review_count} factors under review "
                   f"({', '.join(concerns)}). Risk score: {results.average_risk_score:.1f}, Confidence: {results.average_confidence:.2f}. "
                   f"Consider standard terms with regular review.")
    
    elif decision == "MANUAL_REVIEW":
        # Find the key concerns
        review_factors = [e for e in results.evaluations if e.status.value == "REVIEW"]
        concerns = [e.factor_name for e in review_factors[:3]]
        
        return (f"Manual underwriter review required. Score: {results.weighted_score}%, "
               f"Risk: {results.average_risk_score:.1f}, Confidence: {results.average_confidence:.2f}. "
               f"Key factors to review: {', '.join(concerns)}. "
               f"Rule: {rule_description}. "
               f"Consider: (1) Additional documentation, (2) Higher rate for risk, "
               f"(3) Reduced loan amount, or (4) Co-signer requirement.")
    
    else:  # REJECTED
        if results.fail_count > 0:
            failed = [e.factor_name for e in results.evaluations 
                     if e.status.value == "FAIL"]
            return (f"Application rejected due to failing criteria: {', '.join(failed)}. "
                   f"Risk score: {results.average_risk_score:.1f}. "
                   f"Applicant may reapply after addressing these issues.")
        else:
            return (f"Application rejected. Score: {results.weighted_score}%, "
                   f"Risk: {results.average_risk_score:.1f}, Confidence: {results.average_confidence:.2f}. "
                   f"Rule: {rule_description}. "
                   f"Multiple factors below acceptable thresholds.")
