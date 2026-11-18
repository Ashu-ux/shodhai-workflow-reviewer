"""
Core Data Contracts and Schemas for AI-Assisted Workflow Reviewer.
Preserves artifact versions, evidence locations, and provenance across stages.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any, Union
import json


@dataclass
class SourceRequirement:
    id: str                                  # e.g. "R1", "R2", "R3"
    version: str                             # e.g. "1.0"
    section: str                             # e.g. "RoutingPolicies.md#Section2"
    title: str                               # e.g. "Urgent Ticket Priority"
    condition_dsl: str                       # e.g. "urgency == 'urgent'"
    action: str                              # e.g. "priority_queue"
    precedence: int                          # 1 = highest precedence
    prose: str                               # Source textual policy
    notes: Optional[str] = ""
    evidence_location: str = ""
    is_supported: bool = True
    ambiguity_reason: Optional[str] = None


@dataclass
class StructuredRule:
    rule_id: str
    condition_dsl: str
    action: str
    precedence: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Specification:
    id: str
    version: str
    rules: List[StructuredRule]
    fallback_action: str
    evidence_location: str = ""


@dataclass
class WorkflowNode:
    node_id: str
    type: str                                # "condition" | "action"
    rule_ref: Optional[str] = None
    condition_dsl: Optional[str] = None
    if_true: Optional[str] = None            # Destination node_id or terminal action name
    if_false: Optional[str] = None           # Next node_id
    action: Optional[str] = None             # Terminal action if type == 'action'
    version: str = "1.0"


@dataclass
class WorkflowGraph:
    id: str
    version: str
    entry_node_id: str
    nodes: Dict[str, WorkflowNode]


@dataclass
class LinkedPythonSnippet:
    snippet_id: str
    rule_ref: Optional[str] = None
    version: str = "1.0"
    file_path: str = ""
    entry_function: str = "route_ticket"
    code: str = ""


@dataclass
class ApprovalRecord:
    change_id: str
    target_rule_id: str
    change_type: str                         # "UPDATE_THRESHOLD" | "UPDATE_CONDITION" | "REPLACE_ACTION"
    new_condition_dsl: Optional[str] = None
    new_action: Optional[str] = None
    status: str = "PROPOSED"                 # "APPROVED" | "PROPOSED" | "REJECTED"
    author: str = ""
    timestamp: str = ""
    version_scope: str = "1.0"
    rationale: Optional[str] = ""


@dataclass
class Counterexample:
    ticket_input: Dict[str, Any]
    expected_route: str
    actual_route: str
    violating_rule: Optional[str] = None
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewFinding:
    severity: str                            # "BLOCKER" | "WARNING" | "INFO"
    rule_id: Optional[str]                   # Rule reference or None
    artifact: str                            # "source_requirement" | "specification" | "workflow_graph" | "python_snippet" | "approval_record"
    version: str
    location: str                            # e.g. "WorkflowNode:N3", "route_ticket:line_12"
    description: str
    evidence: str
    correction: str
    counterexample: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewCoverage:
    total_source_requirements: int
    covered_requirements: List[str]
    omitted_requirements: List[str]
    unreviewed_scope: List[str]
    unsupported_features: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceRecord:
    reviewer_version: str = "1.0.0"
    engine: str = "deterministic_semantic_ast"
    model_name: Optional[str] = None
    model_mode: Optional[str] = None
    prompt_hash: Optional[str] = None
    response_hash: Optional[str] = None
    latency_ms: float = 0.0
    retries: int = 0
    token_usage: Dict[str, int] = field(default_factory=dict)
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewReport:
    status: str                              # "PASS" | "CHANGES_REQUIRED" | "INCOMPLETE"
    summary: str
    findings: List[ReviewFinding]
    coverage: ReviewCoverage
    check_results: List[Dict[str, Any]]
    provenance: ProvenanceRecord
    timestamp: str
    bundle_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "coverage": self.coverage.to_dict(),
            "check_results": self.check_results,
            "provenance": self.provenance.to_dict(),
            "timestamp": self.timestamp,
            "bundle_id": self.bundle_id,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class ReviewBundle:
    bundle_id: str
    name: str
    description: str
    source_requirements: List[SourceRequirement]
    specification: Optional[Specification] = None
    workflow_graph: Optional[WorkflowGraph] = None
    python_snippets: List[LinkedPythonSnippet] = field(default_factory=list)
    approval_records: List[ApprovalRecord] = field(default_factory=list)
    expected_status: str = "PASS"
    expected_defects: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    is_frozen: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "name": self.name,
            "description": self.description,
            "source_requirements": [asdict(r) for r in self.source_requirements],
            "specification": asdict(self.specification) if self.specification else None,
            "workflow_graph": asdict(self.workflow_graph) if self.workflow_graph else None,
            "python_snippets": [asdict(s) for s in self.python_snippets],
            "approval_records": [asdict(a) for a in self.approval_records],
            "expected_status": self.expected_status,
            "expected_defects": self.expected_defects,
            "tags": self.tags,
            "is_frozen": self.is_frozen,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReviewBundle":
        source_reqs = [SourceRequirement(**r) for r in data.get("source_requirements", [])]
        
        spec_data = data.get("specification")
        spec = None
        if spec_data:
            rules = [StructuredRule(**r) for r in spec_data.get("rules", [])]
            spec = Specification(
                id=spec_data["id"],
                version=spec_data["version"],
                rules=rules,
                fallback_action=spec_data["fallback_action"],
                evidence_location=spec_data.get("evidence_location", "")
            )
            
        wf_data = data.get("workflow_graph")
        wf = None
        if wf_data:
            nodes = {nid: WorkflowNode(**n) for nid, n in wf_data.get("nodes", {}).items()}
            wf = WorkflowGraph(
                id=wf_data["id"],
                version=wf_data["version"],
                entry_node_id=wf_data["entry_node_id"],
                nodes=nodes
            )
            
        snippets = [LinkedPythonSnippet(**s) for s in data.get("python_snippets", [])]
        approvals = [ApprovalRecord(**a) for a in data.get("approval_records", [])]
        
        return cls(
            bundle_id=data["bundle_id"],
            name=data["name"],
            description=data.get("description", ""),
            source_requirements=source_reqs,
            specification=spec,
            workflow_graph=wf,
            python_snippets=snippets,
            approval_records=approvals,
            expected_status=data.get("expected_status", "PASS"),
            expected_defects=data.get("expected_defects", []),
            tags=data.get("tags", []),
            is_frozen=data.get("is_frozen", False),
        )
