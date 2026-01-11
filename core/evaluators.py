"""
LAYER 2: LLM Ensemble Evaluators

Replaced single LLM micro-evaluator with LLM ensemble system:
- Multiple role-specific LLMs queried in parallel
- Structured JSON outputs (decision, risk_score, confidence, notes)
- Ensemble aggregation (majority vote, averaged risk_score/confidence)
- Deterministic verification with override capability
"""
import json
import re
import logging
from typing import List, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from config.factors import FACTORS, Status, evaluate_with_threshold
from config.llm_config import get_llm_for_role
from core.data_extractor import ExtractedData

logger = logging.getLogger(__name__)


@dataclass
class Evaluation:
    """Result of evaluating a single factor with ensemble system."""
    factor_id: str
    factor_name: str
    category: str
    value: str
    status: Status  # PASS, REVIEW, FAIL
    weight: float
    criteria: str
    notes: str
    risk_score: float = 50.0  # 0-100, higher = more risky
    confidence: float = 0.5  # 0-1, higher = more confident
    source: str = "ensemble"  # 'ensemble'|'threshold'|'threshold_override'
    disagreement: bool = False  # True if ensemble disagreed with deterministic but was overridden


class LLMEnsembleEvaluator:
    """
    LLM Ensemble Evaluator with deterministic verification.
    
    Queries multiple role-specific LLMs in parallel, aggregates their responses,
    and verifies against deterministic thresholds with override capability.
    """
    
    def __init__(
        self,
        roles: List[str] = None,
        use_threshold_override: bool = True,
        confidence_override_threshold: float = 0.7
    ):
        """
        Args:
            roles: List of roles to query as ensemble (e.g., ["factor_analyzer", "risk_synthesizer", "decision_maker"])
            use_threshold_override: When deterministic threshold disagrees, allow deterministic override when confidence low
            confidence_override_threshold: If ensemble average confidence < this, deterministic wins on disagreement
        """
        self.roles = roles or ["factor_analyzer", "risk_synthesizer", "decision_maker"]
        self.use_threshold_override = use_threshold_override
        self.confidence_override_threshold = confidence_override_threshold
        # Lazy-load LLM clients
        self._llms = {}
    
    def _get_llm(self, role: str):
        """Get or create LLM client for role."""
        if role not in self._llms:
            self._llms[role] = get_llm_for_role(role)
        return self._llms[role]
    
    def _build_prompt(self, factor_id: str, value: Any, criteria: str, role: str) -> str:
        """Build role-specific prompt requesting structured JSON output."""
        factor = FACTORS.get(factor_id)
        factor_name = factor.name if factor else factor_id
        
        if role == "factor_analyzer":
            # Math-focused: Emphasize numeric comparison and threshold logic
            prompt = f"""You are a credit risk analyst specializing in numeric analysis. Focus on EXACT mathematical comparisons.

Factor: {factor_name}
Value: {value}
Criteria: {criteria}

CRITICAL INSTRUCTIONS - READ CAREFULLY:
1. For "≤" (less than or equal) criteria: A SMALLER value is BETTER and should PASS
   - Example: If criteria is "≤36%", then 8.2% PASSES because 8.2 < 36
   - Example: If criteria is "≤36%", then 50% FAILS because 50 > 36

2. For "≥" (greater than or equal) criteria: A LARGER value is BETTER and should PASS
   - Example: If criteria is "≥100%", then 299% PASSES because 299 > 100
   - Example: If criteria is "≥100%", then 50% FAILS because 50 < 100

3. Extract the numeric value and compare it STEP BY STEP:
   Step 1: What is the numeric value? (e.g., 8.2)
   Step 2: What is the threshold? (e.g., 36)
   Step 3: What is the comparison operator? (e.g., ≤ means "should be less than or equal")
   Step 4: Does the value satisfy the condition? (e.g., 8.2 ≤ 36? YES → PASS)

Respond in strict JSON format with these keys:
- decision: "PASS", "REVIEW", or "FAIL" based on threshold comparison
- risk_score: number 0-100 (higher = more risky). Use lower scores (0-30) for PASS, medium (30-70) for REVIEW, higher (70-100) for FAIL
- confidence: number 0-1 (0 = low confidence, 1 = high confidence). Use high confidence (0.8-1.0) when the comparison is clear
- notes: brief justification that explicitly shows the comparison (e.g., "8.2% ≤ 36% threshold: PASS")

Example 1: {{ "decision":"PASS", "risk_score":15, "confidence":0.95, "notes":"8.2% ≤ 36% threshold: clearly passes" }}
Example 2: {{ "decision":"PASS", "risk_score":10, "confidence":0.98, "notes":"299.5% ≥ 100% threshold: well above minimum" }}

Your response (JSON only):"""
        
        elif role == "risk_synthesizer":
            # Reasoning-focused: Consider context, patterns, risk synthesis
            prompt = f"""You are a risk assessment specialist. Analyze this factor considering broader risk patterns and context.

Factor: {factor_name}
Value: {value}
Criteria: {criteria}

Your task: Evaluate this factor considering:
- How this factor relates to overall loan risk
- Patterns and trends (e.g., high utilization might indicate financial stress)
- Contextual risk implications (not just threshold checking)
- What this value suggests about the applicant's financial behavior

IMPORTANT: First verify the numeric comparison is correct:
- For DTI ratio: LOWER is BETTER (8.2% is excellent, 50% is concerning)
- For Asset ratios: HIGHER is BETTER (299% is excellent, 20% is concerning)
- Always check if the value meets or exceeds the threshold in the correct direction

Respond in strict JSON format with these keys:
- decision: "PASS", "REVIEW", or "FAIL" based on risk assessment
- risk_score: number 0-100 (higher = more risky). Consider risk implications, not just threshold compliance
- confidence: number 0-1 (0 = low confidence, 1 = high confidence). Reflect how certain you are about the risk assessment
- notes: brief explanation of the risk reasoning and what patterns/context you considered

Example: {{ "decision":"REVIEW", "risk_score":45, "confidence":0.75, "notes":"DTI ratio of 38% is borderline; while technically within review range, indicates limited financial flexibility" }}

Your response (JSON only):"""
        
        elif role == "decision_maker":
            # Decision-focused: Clear recommendations with balanced judgment
            prompt = f"""You are a loan decision specialist. Provide clear, balanced recommendations for loan approval decisions.

Factor: {factor_name}
Value: {value}
Criteria: {criteria}

CRITICAL: Verify mathematical logic before making recommendation:
- DTI (Debt-to-Income): LOWER percentages are BETTER (5% is excellent, 50% is high risk)
- Asset Ratios: HIGHER percentages are BETTER (300% is excellent, 20% is concerning)
- Always double-check: does this value meet the pass threshold?

Your task: Make a clear decision recommendation by:
- Considering both the numeric thresholds AND practical lending implications
- Balancing risk tolerance with reasonable lending standards
- Providing actionable guidance (what should happen next)
- Being decisive when clear, cautious when borderline

Respond in strict JSON format with these keys:
- decision: "PASS", "REVIEW", or "FAIL" - make a clear recommendation
- risk_score: number 0-100 (higher = more risky). Reflect the decision-relevant risk level
- confidence: number 0-1 (0 = low confidence, 1 = high confidence). Reflect your confidence in the recommendation
- notes: brief recommendation that explains the decision rationale and any next steps needed

Example: {{ "decision":"PASS", "risk_score":20, "confidence":0.90, "notes":"Strong credit score exceeds threshold significantly. Recommend approval with standard terms." }}

Your response (JSON only):"""
        
        else:
            # Fallback generic prompt
            prompt = f"""Analyze this loan application factor.

Factor: {factor_name}
Value: {value}
Criteria: {criteria}

Please respond in strict JSON format with these keys:
- decision: one of "PASS", "REVIEW", "FAIL"
- risk_score: number 0-100 (higher = more risky)
- confidence: number 0-1 (0 = low confidence, 1 = high confidence)
- notes: brief textual justification referencing numeric facts

Example: {{ "decision":"PASS", "risk_score":12.3, "confidence":0.92, "notes":"Credit score of 720 exceeds the 700 threshold." }}

Your response (JSON only):"""
        
        return prompt
    
    def _invoke_llm(self, role: str, prompt: str) -> Dict[str, Any]:
        """Invoke single LLM role and parse JSON response."""
        try:
            llm = self._get_llm(role)
            response = llm.invoke(prompt)
            content = response.content.strip() if hasattr(response, 'content') else str(response)
            
            # Try parsing JSON directly
            try:
                parsed = json.loads(content)
                return parsed
            except json.JSONDecodeError:
                # Try to extract JSON blob from text
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', content, re.DOTALL)
                if json_match:
                    try:
                        return json.loads(json_match.group(0))
                    except json.JSONDecodeError:
                        pass
                
                # Fallback: return conservative REVIEW with low confidence
                logger.warning(f"Failed to parse JSON from {role}, using fallback")
                return {"decision": "REVIEW", "risk_score": 50.0, "confidence": 0.3, "notes": content[:500]}
                
        except Exception as e:
            logger.exception(f"LLM role {role} failed: {e}")
            return {"decision": "REVIEW", "risk_score": 50.0, "confidence": 0.2, "notes": f"llm_error:{str(e)[:100]}"}
    
    def evaluate_factor(self, factor_id: str, raw_value: Any, display_value: str) -> Evaluation:
        """
        Evaluate a single factor using ensemble of LLMs.
        
        Returns Evaluation with ensemble-aggregated results, verified against deterministic thresholds.
        """
        factor = FACTORS.get(factor_id)
        if not factor:
            return Evaluation(
                factor_id=factor_id,
                factor_name="Unknown",
                category="Unknown",
                value=str(display_value),
                status=Status.REVIEW,
                weight=0.0,
                criteria="",
                notes="Unknown factor",
                risk_score=50.0,
                confidence=0.0,
                source="threshold"
            )
        
        # Call ensemble in parallel with role-specific prompts
        ensemble_results = []
        with ThreadPoolExecutor(max_workers=len(self.roles)) as executor:
            futures = {
                executor.submit(
                    self._invoke_llm, 
                    role, 
                    self._build_prompt(factor_id, raw_value, factor.criteria_text, role)
                ): role 
                for role in self.roles
            }
            
            for future in as_completed(futures):
                role = futures[future]
                try:
                    parsed = future.result()
                    decision = parsed.get("decision", "REVIEW").upper()
                    # Normalize decision to Status enum values
                    if decision == "PASS":
                        decision = "PASS"
                    elif decision == "FAIL":
                        decision = "FAIL"
                    else:
                        decision = "REVIEW"
                    
                    try:
                        risk_score = float(parsed.get("risk_score", 50.0))
                        risk_score = max(0.0, min(100.0, risk_score))  # Clamp to 0-100
                    except (ValueError, TypeError):
                        risk_score = 50.0
                    
                    try:
                        confidence = float(parsed.get("confidence", 0.3))
                        confidence = max(0.0, min(1.0, confidence))  # Clamp to 0-1
                    except (ValueError, TypeError):
                        confidence = 0.3
                    
                    notes = str(parsed.get("notes", ""))[:500]
                    
                    ensemble_results.append({
                        "role": role,
                        "decision": decision,
                        "risk_score": risk_score,
                        "confidence": confidence,
                        "notes": notes
                    })
                except Exception as e:
                    logger.exception(f"Error processing {role} result: {e}")
                    ensemble_results.append({
                        "role": role,
                        "decision": "REVIEW",
                        "risk_score": 50.0,
                        "confidence": 0.2,
                        "notes": f"error:{str(e)[:100]}"
                    })
        
        # Aggregate ensemble: majority vote + averages
        if not ensemble_results:
            # Complete failure - use deterministic
            deterministic_status = evaluate_with_threshold(factor_id, raw_value)
            return Evaluation(
                factor_id=factor_id,
                factor_name=factor.name,
                category=factor.category,
                value=display_value,
                status=deterministic_status,
                weight=factor.weight,
                criteria=factor.criteria_text,
                notes="Ensemble failed, using deterministic evaluation",
                risk_score=50.0 if deterministic_status == Status.REVIEW else (25.0 if deterministic_status == Status.PASS else 75.0),
                confidence=0.0,
                source="threshold"
            )
        
        # Majority vote
        decision_counts = {"PASS": 0, "REVIEW": 0, "FAIL": 0}
        for r in ensemble_results:
            decision_counts[r["decision"]] += 1
        majority_decision = max(decision_counts.items(), key=lambda x: x[1])[0]
        
        # Averages
        avg_risk = sum(r["risk_score"] for r in ensemble_results) / len(ensemble_results)
        avg_conf = sum(r["confidence"] for r in ensemble_results) / len(ensemble_results)
        
        # Combine notes (take first one that's not error)
        notes = next((r["notes"] for r in ensemble_results if r["notes"] and not r["notes"].startswith("error:")), ensemble_results[0]["notes"])
        
        # Deterministic verification
        deterministic_status = evaluate_with_threshold(factor_id, raw_value)
        deterministic_decision = deterministic_status.value
        
        source = "ensemble"
        final_decision = majority_decision
        disagreement = False
        
        # Check for disagreement
        if majority_decision != deterministic_decision:
            disagreement = True
            
            # If ensemble confidence is low OR we explicitly configured deterministic override, prefer deterministic
            if self.use_threshold_override and avg_conf < self.confidence_override_threshold:
                # Override with deterministic
                final_decision = deterministic_decision
                source = "threshold_override"
                notes = f"Ensemble({majority_decision}) avg_conf={avg_conf:.2f} overridden by deterministic({deterministic_decision}) | {notes}"
            else:
                # Ensemble confident but still disagrees -> keep ensemble but mark disagreement
                source = "ensemble"
                notes = f"[Ensemble vs threshold disagreement] {notes}"
        
        # Convert decision string to Status enum
        status_map = {"PASS": Status.PASS, "FAIL": Status.FAIL, "REVIEW": Status.REVIEW}
        final_status = status_map.get(final_decision, Status.REVIEW)
        
        return Evaluation(
            factor_id=factor_id,
            factor_name=factor.name,
            category=factor.category,
            value=display_value,
            status=final_status,
            weight=factor.weight,
            criteria=factor.criteria_text,
            notes=notes,
            risk_score=avg_risk,
            confidence=avg_conf,
            source=source,
            disagreement=disagreement
        )


def run_all_evaluations(
    evaluator: LLMEnsembleEvaluator,
    data: ExtractedData
) -> List[Evaluation]:
    """
    Run all factor evaluations using ensemble evaluator in parallel.
    Returns list of Evaluation results.
    """
    # Map factor IDs to their values from extracted data
    factor_values = {
        "credit_score": (data.credit_score, f"Score: {data.credit_score}"),
        "payment_history": (data.payment_history_pct, f"{data.payment_history_pct}% on-time"),
        "credit_utilization": (data.credit_utilization_pct, f"{data.credit_utilization_pct}% used"),
        "hard_inquiries": (data.hard_inquiries, f"{data.hard_inquiries} inquiries"),
        "employment_status": (data.employment_status, data.employment_status),
        "employment_duration": (data.employment_duration_years, f"{data.employment_duration_years} years"),
        "annual_income": (data.annual_income, f"${data.annual_income:,.0f}"),
        "dti_ratio": (data.dti_ratio, f"{data.dti_ratio}%"),
        "existing_loans": (data.existing_loan_count, f"{data.existing_loan_count} active loans"),
        "liquid_assets_ratio": (data.liquid_assets_ratio, f"{data.liquid_assets_ratio}% of loan amount"),
        "collateral_offered": (data.collateral_offered, data.collateral_offered),
        "bank_relationship": (data.bank_relationship_years, f"{data.bank_relationship_years} years"),
        "nsf_count": (data.nsf_count, f"{data.nsf_count} in 12 months"),
        "monthly_cash_flow": (data.monthly_cash_flow, f"${data.monthly_cash_flow:+,.0f}/month"),
        "docs_verified_pct": (data.docs_verified_pct, f"{data.docs_verified_pct}% verified"),
        "identity_verified": (data.identity_verified, "Verified" if data.identity_verified else "Not verified"),
    }
    
    results = []
    
    # Run evaluations in parallel
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        
        for factor_id, (raw_value, display_value) in factor_values.items():
            if factor_id not in FACTORS:
                continue
            
            future = executor.submit(
                evaluator.evaluate_factor,
                factor_id,
                raw_value,
                display_value
            )
            futures[future] = factor_id
        
        for future in as_completed(futures):
            try:
                evaluation = future.result()
                results.append(evaluation)
            except Exception as e:
                logger.exception(f"Error evaluating factor: {e}")
                factor_id = futures[future]
                factor = FACTORS.get(factor_id)
                if factor:
                    # Fallback to deterministic
                    raw_value = factor_values[factor_id][0]
                    display_value = factor_values[factor_id][1]
                    deterministic_status = evaluate_with_threshold(factor_id, raw_value)
                    results.append(Evaluation(
                        factor_id=factor_id,
                        factor_name=factor.name,
                        category=factor.category,
                        value=display_value,
                        status=deterministic_status,
                        weight=factor.weight,
                        criteria=factor.criteria_text,
                        notes=f"Evaluation error: {str(e)[:100]}",
                        risk_score=50.0,
                        confidence=0.0,
                        source="threshold"
                    ))
    
    # Sort by category for consistent output
    category_order = [
        "Credit Profile",
        "Income & Employment",
        "Debt & Obligations",
        "Assets & Collateral",
        "Banking & Relationship",
        "Documentation"
    ]
    
    def sort_key(e):
        try:
            return category_order.index(e.category)
        except ValueError:
            return 999
    
    results.sort(key=sort_key)
    
    return results


def run_evaluations_sync(
    evaluator: LLMEnsembleEvaluator,
    data: ExtractedData
) -> List[Evaluation]:
    """
    Run evaluations sequentially (for debugging or when parallel fails).
    """
    factor_values = {
        "credit_score": (data.credit_score, f"Score: {data.credit_score}"),
        "payment_history": (data.payment_history_pct, f"{data.payment_history_pct}% on-time"),
        "credit_utilization": (data.credit_utilization_pct, f"{data.credit_utilization_pct}% used"),
        "hard_inquiries": (data.hard_inquiries, f"{data.hard_inquiries} inquiries"),
        "employment_status": (data.employment_status, data.employment_status),
        "employment_duration": (data.employment_duration_years, f"{data.employment_duration_years} years"),
        "annual_income": (data.annual_income, f"${data.annual_income:,.0f}"),
        "dti_ratio": (data.dti_ratio, f"{data.dti_ratio}%"),
        "existing_loans": (data.existing_loan_count, f"{data.existing_loan_count} active loans"),
        "liquid_assets_ratio": (data.liquid_assets_ratio, f"{data.liquid_assets_ratio}% of loan amount"),
        "collateral_offered": (data.collateral_offered, data.collateral_offered),
        "bank_relationship": (data.bank_relationship_years, f"{data.bank_relationship_years} years"),
        "nsf_count": (data.nsf_count, f"{data.nsf_count} in 12 months"),
        "monthly_cash_flow": (data.monthly_cash_flow, f"${data.monthly_cash_flow:+,.0f}/month"),
        "docs_verified_pct": (data.docs_verified_pct, f"{data.docs_verified_pct}% verified"),
        "identity_verified": (data.identity_verified, "Verified" if data.identity_verified else "Not verified"),
    }
    
    results = []
    
    for factor_id, (raw_value, display_value) in factor_values.items():
        if factor_id not in FACTORS:
            continue
        
        try:
            evaluation = evaluator.evaluate_factor(factor_id, raw_value, display_value)
            results.append(evaluation)
        except Exception as e:
            logger.exception(f"Error evaluating {factor_id}: {e}")
            factor = FACTORS[factor_id]
            deterministic_status = evaluate_with_threshold(factor_id, raw_value)
            results.append(Evaluation(
                factor_id=factor_id,
                factor_name=factor.name,
                category=factor.category,
                value=display_value,
                status=deterministic_status,
                weight=factor.weight,
                criteria=factor.criteria_text,
                notes=f"Evaluation error: {str(e)[:100]}",
                risk_score=50.0,
                confidence=0.0,
                source="threshold"
            ))
    
    return results
