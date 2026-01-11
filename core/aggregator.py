"""
LAYER 3: Aggregator

Pure Python - collects all evaluation results and calculates:
- Pass/Review/Fail counts
- Weighted score (incorporates risk_score weighting)
- Average risk_score and confidence
- Category summaries
"""
from dataclasses import dataclass
from typing import List, Dict
from config.factors import Status
from core.evaluators import Evaluation


@dataclass
class AggregatedResults:
    """Aggregated evaluation results with ensemble metrics."""
    
    # Counts
    total_factors: int = 0
    pass_count: int = 0
    review_count: int = 0
    fail_count: int = 0
    
    # Score (weighted by status, adjusted by risk_score)
    weighted_score: float = 0.0
    total_weight: float = 0.0
    
    # Ensemble metrics
    average_risk_score: float = 50.0  # 0-100, average across all factors
    average_confidence: float = 0.5  # 0-1, average across all factors
    
    # All evaluations
    evaluations: List[Evaluation] = None
    
    # By category
    category_summaries: Dict[str, dict] = None
    
    # Concerns and strengths
    concerns: List[str] = None
    strengths: List[str] = None


def aggregate_results(evaluations: List[Evaluation]) -> AggregatedResults:
    """
    Aggregate all evaluation results with risk_score and confidence.
    
    Scoring:
    - PASS = full weight, reduced by risk_score
    - REVIEW = 50% of weight, reduced by risk_score
    - FAIL = 0% of weight
    
    Risk contribution: Higher risk_score reduces weighted_score contribution.
    """
    results = AggregatedResults(
        evaluations=evaluations,
        category_summaries={},
        concerns=[],
        strengths=[]
    )
    
    total_weight = 0.0
    weighted_sum = 0.0  # Risk-adjusted weighted sum
    total_risk = 0.0
    total_confidence = 0.0
    
    for eval in evaluations:
        results.total_factors += 1
        w = eval.weight
        total_weight += w
        
        # Risk contribution: higher risk_score should reduce weighted_score
        # Risk multiplier: (100 - risk_score) / 100
        # e.g., risk_score=25 -> multiplier=0.75, risk_score=75 -> multiplier=0.25
        risk_multiplier = (100.0 - eval.risk_score) / 100.0
        risk_multiplier = max(0.0, min(1.0, risk_multiplier))  # Clamp to 0-1
        
        # Accumulate risk and confidence
        total_risk += eval.risk_score
        total_confidence += eval.confidence
        
        if eval.status == Status.PASS:
            results.pass_count += 1
            # Full weight, adjusted by risk
            weighted_sum += w * risk_multiplier
            results.strengths.append(f"{eval.factor_name}: {eval.notes}")
            
        elif eval.status == Status.FAIL:
            results.fail_count += 1
            # 0 weight for fails (regardless of risk)
            weighted_sum += 0.0
            results.concerns.append(f"❌ {eval.factor_name}: {eval.notes}")
            
        else:  # REVIEW
            results.review_count += 1
            # 50% of weight, adjusted by risk
            weighted_sum += w * 0.5 * risk_multiplier
            results.concerns.append(f"⚠️ {eval.factor_name}: {eval.notes}")
        
        # Aggregate by category
        if eval.category not in results.category_summaries:
            results.category_summaries[eval.category] = {
                "pass": 0,
                "review": 0,
                "fail": 0,
                "factors": []
            }
        
        cat = results.category_summaries[eval.category]
        cat["factors"].append(eval)
        if eval.status == Status.PASS:
            cat["pass"] += 1
        elif eval.status == Status.FAIL:
            cat["fail"] += 1
        else:
            cat["review"] += 1
    
    # Calculate final score
    results.total_weight = total_weight
    if total_weight > 0:
        results.weighted_score = round((weighted_sum / total_weight) * 100, 1)
    
    # Calculate averages
    if len(evaluations) > 0:
        results.average_risk_score = round(total_risk / len(evaluations), 1)
        results.average_confidence = round(total_confidence / len(evaluations), 2)
    
    return results


def get_risk_level(results: AggregatedResults) -> str:
    """Determine risk level based on results (uses average_risk_score)."""
    if results.fail_count > 0:
        return "HIGH"
    elif results.average_risk_score < 30:
        return "LOW"
    elif results.average_risk_score < 50:
        return "MEDIUM-LOW"
    elif results.average_risk_score < 70:
        return "MEDIUM"
    else:
        return "MEDIUM-HIGH"
