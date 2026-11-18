"""
Workflow Graph Traversal and Structural Reachability Analyzer.
Verifies entry point, DAG properties, reachability, dead branches,
and extracts reachable decision paths.
"""

from typing import Dict, List, Set, Tuple, Optional, Any
from src.contracts.models import WorkflowGraph, WorkflowNode


class GraphTraversalAnalyzer:
    """Performs static structural and reachability analysis on WorkflowGraph."""

    @classmethod
    def analyze(cls, graph: WorkflowGraph) -> Dict[str, Any]:
        nodes = graph.nodes
        entry_id = graph.entry_node_id

        errors: List[str] = []
        warnings: List[str] = []

        if entry_id not in nodes:
            return {
                "is_valid": False,
                "reachable_nodes": set(),
                "unreachable_nodes": set(nodes.keys()),
                "terminal_paths": [],
                "errors": [f"Entry node '{entry_id}' does not exist in graph nodes."],
                "warnings": warnings,
            }

        # 1. Reachability traversal via BFS/DFS
        visited: Set[str] = set()
        queue = [entry_id]
        has_cycle = False
        recursion_stack: Set[str] = set()

        def detect_cycle(curr_id: str, stack: Set[str], seen: Set[str]) -> bool:
            if curr_id in stack:
                return True
            if curr_id in seen or curr_id not in nodes:
                return False
            
            seen.add(curr_id)
            stack.add(curr_id)
            node = nodes[curr_id]
            if node.type == "condition":
                if node.if_true and node.if_true in nodes:
                    if detect_cycle(node.if_true, stack, seen):
                        return True
                if node.if_false and node.if_false in nodes:
                    if detect_cycle(node.if_false, stack, seen):
                        return True
            stack.remove(curr_id)
            return False

        has_cycle = detect_cycle(entry_id, set(), set())
        if has_cycle:
            errors.append("Workflow graph contains cyclic loops; routing policies must form a DAG.")

        # Traverse reachable nodes
        visited_nodes: Set[str] = set()
        queue = [entry_id]
        while queue:
            curr_id = queue.pop(0)
            if curr_id in visited_nodes or curr_id not in nodes:
                continue
            visited_nodes.add(curr_id)
            node = nodes[curr_id]
            if node.type == "condition":
                if node.if_true:
                    if node.if_true in nodes:
                        queue.append(node.if_true)
                if node.if_false:
                    if node.if_false in nodes:
                        queue.append(node.if_false)
                    else:
                        errors.append(f"Condition node '{curr_id}' references missing if_false destination '{node.if_false}'.")
                else:
                    errors.append(f"Condition node '{curr_id}' is missing if_false branch.")

        unreachable_nodes = set(nodes.keys()) - visited_nodes
        if unreachable_nodes:
            warnings.append(f"Unreachable / dead workflow nodes detected: {sorted(list(unreachable_nodes))}.")

        # 2. Extract reachable decision paths from entry to terminals
        paths: List[List[Tuple[str, bool, Optional[str]]]] = []

        def trace_paths(curr_id: str, current_path: List[Tuple[str, bool, Optional[str]]]):
            # Cycle prevention
            visited_ids = {p[0] for p in current_path}
            if curr_id in visited_ids:
                return

            if curr_id not in nodes:
                # Terminal action directly referenced
                paths.append(current_path + [(curr_id, True, curr_id)])
                return
            
            node = nodes[curr_id]
            if node.type == "action":
                paths.append(current_path + [(curr_id, True, node.action or curr_id)])
                return
            
            # Condition node
            if node.if_true:
                if node.if_true in nodes:
                    target_node = nodes[node.if_true]
                    act = target_node.action if target_node.type == "action" else None
                    trace_paths(node.if_true, current_path + [(curr_id, True, act)])
                else:
                    # if_true directly names terminal action
                    trace_paths(node.if_true, current_path + [(curr_id, True, node.if_true)])
                    
            if node.if_false:
                if node.if_false in nodes:
                    trace_paths(node.if_false, current_path + [(curr_id, False, None)])
                else:
                    trace_paths(node.if_false, current_path + [(curr_id, False, node.if_false)])

        if not has_cycle:
            trace_paths(entry_id, [])

        return {
            "is_valid": len(errors) == 0,
            "reachable_nodes": visited_nodes,
            "unreachable_nodes": unreachable_nodes,
            "terminal_paths": paths,
            "errors": errors,
            "warnings": warnings,
        }
