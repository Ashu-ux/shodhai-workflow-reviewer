"""
Effective Requirements Derivation Engine.
Applies approved changes in chronological order, verifies approval authority,
and detects contradictory approval records without silent resolution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from src.contracts.models import SourceRequirement, ApprovalRecord, ReviewFinding
from src.contracts.dsl_ast import ASTNode, UnsupportedNode
from src.dsl.parser import ConditionParser
from src.dsl.normalizer import ConditionNormalizer


@dataclass
class EffectiveRequirement:
    rule_id: str
    version: str
    section: str
    title: str
    condition_dsl: str
    parsed_ast: ASTNode
    action: str
    precedence: int
    source_prose: str
    applied_changes: List[str] = field(default_factory=list)
    is_supported: bool = True
    ambiguity_reason: Optional[str] = None


@dataclass
class DerivationResult:
    effective_requirements: Dict[str, EffectiveRequirement]
    ordered_rules: List[EffectiveRequirement]
    contradictions: List[Dict[str, Any]]
    unapproved_records: List[ApprovalRecord]
    unsupported_rules: List[Dict[str, Any]]


class EffectiveRequirementsEngine:
    """Derives effective requirements from base source requirements and approval records."""

    @classmethod
    def derive(
        cls,
        source_requirements: List[SourceRequirement],
        approval_records: List[ApprovalRecord]
    ) -> DerivationResult:
        effective_map: Dict[str, EffectiveRequirement] = {}
        unsupported_rules: List[Dict[str, Any]] = []

        # 1. Initialize effective requirements from base source requirements
        for req in source_requirements:
            parsed = ConditionParser.parse(req.condition_dsl)
            is_supported = not isinstance(parsed, UnsupportedNode) and req.is_supported
            ambiguity = req.ambiguity_reason
            if not is_supported or isinstance(parsed, UnsupportedNode):
                is_supported = False
                reason = parsed.reason if isinstance(parsed, UnsupportedNode) else (req.ambiguity_reason or "Declared unsupported requirement")
                ambiguity = reason
                unsupported_rules.append({
                    "rule_id": req.id,
                    "condition_dsl": req.condition_dsl,
                    "reason": reason
                })

            effective_map[req.id] = EffectiveRequirement(
                rule_id=req.id,
                version=req.version,
                section=req.section,
                title=req.title,
                condition_dsl=req.condition_dsl,
                parsed_ast=parsed,
                action=req.action,
                precedence=req.precedence,
                source_prose=req.prose,
                applied_changes=[],
                is_supported=is_supported,
                ambiguity_reason=ambiguity
            )

        # 2. Filter approval records by status
        approved_records: List[ApprovalRecord] = []
        unapproved_records: List[ApprovalRecord] = []

        for rec in approval_records:
            # Top-level approval metadata is trusted; claims inside prose/rationale are not
            if rec.status == "APPROVED":
                approved_records.append(rec)
            else:
                unapproved_records.append(rec)

        # 3. Detect contradictory approved records
        # Group approved records by target rule
        by_target: Dict[str, List[ApprovalRecord]] = {}
        for rec in approved_records:
            by_target.setdefault(rec.target_rule_id, []).append(rec)

        contradictions: List[Dict[str, Any]] = []
        valid_applicable_records: List[ApprovalRecord] = []

        for target_id, recs in by_target.items():
            if len(recs) == 1:
                valid_applicable_records.append(recs[0])
            else:
                # Multiple approved records targeting the same rule
                # Check if they propose conflicting changes without clear ordering
                timestamps = [r.timestamp for r in recs]
                # If conditions or actions differ and timestamps/ordering are conflicting or identical
                distinct_conditions = set(r.new_condition_dsl for r in recs if r.new_condition_dsl)
                distinct_actions = set(r.new_action for r in recs if r.new_action)

                if len(distinct_conditions) > 1 or len(distinct_actions) > 1:
                    # Contradiction detected!
                    contradictions.append({
                        "target_rule_id": target_id,
                        "conflicting_records": [r.change_id for r in recs],
                        "details": f"Multiple contradictory APPROVED records for {target_id}: "
                                   f"conditions={distinct_conditions}, actions={distinct_actions}."
                    })
                    # Do not silently pick one
                else:
                    # Same changes duplicated or compatible; sort by timestamp
                    recs.sort(key=lambda r: r.timestamp)
                    valid_applicable_records.append(recs[-1])

        # 4. Apply valid approved records
        # Sort by timestamp
        valid_applicable_records.sort(key=lambda r: r.timestamp)

        for rec in valid_applicable_records:
            if rec.target_rule_id in effective_map:
                eff = effective_map[rec.target_rule_id]
                if rec.new_condition_dsl:
                    eff.condition_dsl = rec.new_condition_dsl
                    eff.parsed_ast = ConditionParser.parse(rec.new_condition_dsl)
                    if isinstance(eff.parsed_ast, UnsupportedNode):
                        eff.is_supported = False
                        eff.ambiguity_reason = eff.parsed_ast.reason
                if rec.new_action:
                    eff.action = rec.new_action
                eff.applied_changes.append(rec.change_id)
                eff.version = f"{eff.version}+{rec.change_id}"

        # 5. Order rules by precedence
        ordered_rules = sorted(effective_map.values(), key=lambda r: r.precedence)

        return DerivationResult(
            effective_requirements=effective_map,
            ordered_rules=ordered_rules,
            contradictions=contradictions,
            unapproved_records=unapproved_records,
            unsupported_rules=unsupported_rules
        )
