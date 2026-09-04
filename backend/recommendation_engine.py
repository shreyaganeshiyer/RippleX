from dataclasses import dataclass
from typing import Any, Sequence


# ============================================================
# DECISION POLICY
# ============================================================
#
# RippleX uses deterministic business rules for recommendations.
# These weights are intentionally explicit so the decision policy
# is transparent, reviewable, and easy to tune.
#
# Higher score = stronger recommendation.
#
# Priority:
#   1. Protect/recover more customer units.
#   2. Protect more affected orders.
#   3. Minimize recovery cost.
#
# These are planning weights, not external factual claims.
#

UNIT_RECOVERY_WEIGHT = 10.0
ORDER_PROTECTION_WEIGHT = 25.0
COST_PENALTY_WEIGHT = 0.01


# ============================================================
# RECOMMENDATION MODEL
# ============================================================


@dataclass(frozen=True)
class Recommendation:
    """
    Final deterministic recommendation produced by RippleX.

    The recommendation is based exclusively on response options
    generated from the deterministic impact assessment.

    No LLM is used to calculate or select the recommendation.
    """

    recommended_option_type: str
    title: str
    reasoning: str

    expected_units_recovered: int
    orders_protected: int

    estimated_cost: float
    tradeoff: str

    confidence: float

    evidence: tuple[Any, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the recommendation into the API response format.
        """

        return {
            "recommended_option_type": (
                self.recommended_option_type
            ),
            "title": self.title,
            "reasoning": self.reasoning,
            "expected_units_recovered": (
                self.expected_units_recovered
            ),
            "orders_protected": self.orders_protected,
            "estimated_cost": self.estimated_cost,
            "tradeoff": self.tradeoff,
            "confidence": self.confidence,
            "evidence": [
                evidence.to_dict()
                if hasattr(evidence, "to_dict")
                else evidence
                for evidence in self.evidence
            ],
        }


# ============================================================
# OPTION SCORING
# ============================================================


def _option_score(option: Any) -> float:
    """
    Calculate the deterministic business score for a response
    option.

    Infeasible options are never eligible for recommendation.

    Score =
        units recovered/protected
        + orders protected
        - estimated cost penalty
    """

    if not getattr(option, "feasible", False):
        return float("-inf")

    units = max(
        float(getattr(option, "units_recovered", 0)),
        0.0,
    )

    orders = max(
        float(getattr(option, "orders_helped", 0)),
        0.0,
    )

    cost = max(
        float(getattr(option, "estimated_cost", 0)),
        0.0,
    )

    return (
        units * UNIT_RECOVERY_WEIGHT
        + orders * ORDER_PROTECTION_WEIGHT
        - cost * COST_PENALTY_WEIGHT
    )


# ============================================================
# CONFIDENCE
# ============================================================


def _calculate_confidence(
    ranked_options: Sequence[Any],
) -> float:
    """
    Estimate recommendation confidence from the separation
    between the best and second-best feasible options.

    Confidence represents how clearly the deterministic policy
    prefers the selected option. It is not model confidence.
    """

    if not ranked_options:
        return 0.0

    if len(ranked_options) == 1:
        return 0.90

    best_score = _option_score(ranked_options[0])
    second_score = _option_score(ranked_options[1])

    if best_score == float("-inf"):
        return 0.0

    # If both options have exactly zero score, there is no
    # meaningful basis for preferring one over the other.
    if best_score == 0:
        return 0.50

    margin = (
        best_score - second_score
    ) / abs(best_score)

    if margin >= 0.30:
        return 0.95

    if margin >= 0.15:
        return 0.85

    if margin >= 0.05:
        return 0.70

    return 0.55


# ============================================================
# RECOMMENDATION REASONING
# ============================================================


def _build_reasoning(option: Any) -> str:
    """
    Build an explainable recommendation rationale from the
    selected response option.

    No additional business facts are introduced here.
    """

    title = getattr(
        option,
        "title",
        "Selected response",
    )

    units = max(
        int(getattr(option, "units_recovered", 0)),
        0,
    )

    orders = max(
        int(getattr(option, "orders_helped", 0)),
        0,
    )

    cost = max(
        float(getattr(option, "estimated_cost", 0.0)),
        0.0,
    )

    tradeoff = getattr(
        option,
        "tradeoff",
        "Trade-off information is unavailable.",
    )

    return (
        f"{title} is the strongest available response "
        f"under the current deterministic decision policy. "
        f"It is expected to address {units} units across "
        f"{orders} affected orders at an estimated cost of "
        f"₹{cost:,.2f}. "
        f"Trade-off: {tradeoff}"
    )


# ============================================================
# RECOMMENDATION ENGINE
# ============================================================


def recommend_response(
    impact: Any,
    response_options: Sequence[Any],
) -> Recommendation:
    """
    Select the strongest feasible response option.

    Design principles:

    1. Only deterministic response options are evaluated.
    2. Infeasible options cannot be recommended.
    3. No business facts are invented.
    4. The selected recommendation inherits evidence from
       the selected response option.
    5. If nothing can be safely recommended, RippleX escalates
       to human review.

    `impact` is accepted as an explicit input so the public
    interface remains aligned with the broader decision pipeline.
    The current recommendation policy derives its ranking from
    the already-calculated response options.
    """

    # --------------------------------------------------------
    # Defensive handling
    # --------------------------------------------------------

    if response_options is None:
        response_options = ()

    # --------------------------------------------------------
    # Keep only feasible options
    # --------------------------------------------------------

    feasible_options = [
        option
        for option in response_options
        if getattr(option, "feasible", False)
    ]

    # --------------------------------------------------------
    # No safe automated option
    # --------------------------------------------------------

    if not feasible_options:
        return Recommendation(
            recommended_option_type="HUMAN_REVIEW",
            title="Escalate for human review",
            reasoning=(
                "No feasible response option was identified "
                "from the available supply-chain data. "
                "RippleX will not recommend an action without "
                "sufficient evidence of a safe response."
            ),
            expected_units_recovered=0,
            orders_protected=0,
            estimated_cost=0.0,
            tradeoff=(
                "No automated response can be recommended "
                "without a feasible, evidence-backed option."
            ),
            confidence=0.0,
            evidence=(),
        )

    # --------------------------------------------------------
    # Rank options deterministically
    # --------------------------------------------------------

    ranked_options = sorted(
        feasible_options,
        key=_option_score,
        reverse=True,
    )

    best = ranked_options[0]

    # --------------------------------------------------------
    # Calculate confidence from score separation
    # --------------------------------------------------------

    confidence = _calculate_confidence(
        ranked_options
    )

    # --------------------------------------------------------
    # Extract selected option values defensively
    # --------------------------------------------------------

    option_type = str(
        getattr(
            best,
            "option_type",
            "UNKNOWN",
        )
    )

    title = str(
        getattr(
            best,
            "title",
            "Recommended response",
        )
    )

    units_recovered = max(
        int(
            getattr(
                best,
                "units_recovered",
                0,
            )
        ),
        0,
    )

    orders_helped = max(
        int(
            getattr(
                best,
                "orders_helped",
                0,
            )
        ),
        0,
    )

    estimated_cost = max(
        float(
            getattr(
                best,
                "estimated_cost",
                0.0,
            )
        ),
        0.0,
    )

    tradeoff = str(
        getattr(
            best,
            "tradeoff",
            "Trade-off information is unavailable.",
        )
    )

    # --------------------------------------------------------
    # Preserve evidence from the selected response
    # --------------------------------------------------------

    evidence = tuple(
        getattr(
            best,
            "evidence",
            (),
        )
        or ()
    )

    # --------------------------------------------------------
    # Build transparent reasoning
    # --------------------------------------------------------

    reasoning = _build_reasoning(best)

    # --------------------------------------------------------
    # Return final recommendation
    # --------------------------------------------------------

    return Recommendation(
        recommended_option_type=option_type,
        title=title,
        reasoning=reasoning,
        expected_units_recovered=units_recovered,
        orders_protected=orders_helped,
        estimated_cost=estimated_cost,
        tradeoff=tradeoff,
        confidence=confidence,
        evidence=evidence,
    )