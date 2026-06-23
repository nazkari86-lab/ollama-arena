"""Build adjacency data for D3.js force-directed tree."""
from __future__ import annotations
from .db import GenomeStore

_RELATION_COLORS = {
    "fine_tuned_from": "#58a6ff",
    "distilled_from":  "#3fb950",
    "merged_from":     "#f85149",
    "trained_from":    "#e3b341",
    "quantized_from":  "#bc8cff",
}


class GraphEngine:
    def __init__(self, store: GenomeStore):
        self.store = store

    def to_d3(self) -> dict:
        """Return {nodes: [...], links: [...]} for D3 force graph."""
        canonicals = self.store.all_canonical()
        locals_ = self.store.list_local()

        nodes = []
        for m in canonicals:
            nodes.append({
                "id": m["id"], "name": m["name"],
                "family": m.get("family", ""),
                "org": m.get("org", ""),
                "params_b": m.get("architecture", {}).get("params_b", 0),
                "type": "canonical",
            })
        for lm in locals_:
            if lm["genome_id"] is None:
                nodes.append({
                    "id": f"local/{lm['name']}", "name": lm["name"],
                    "family": "Unknown", "org": "Local",
                    "params_b": 0, "type": "local",
                    "confidence": lm["confidence"],
                })

        seen_ids = {n["id"] for n in nodes}
        links = []
        seen_edges: set[tuple[str, str, str]] = set()
        for m in canonicals:
            # get_lineage(id) matches rows where id is EITHER child_id OR
            # parent_id, so the same edge is returned once while processing
            # the child's canonical row and again while processing the
            # parent's — dedupe on (child, parent, relation) to avoid
            # doubling every link in the graph.
            edges = self.store.get_lineage(m["id"])
            for e in edges:
                edge_key = (e["child_id"], e["parent_id"], e["relation"])
                if (e["child_id"] in seen_ids and e["parent_id"] in seen_ids
                        and e["child_id"] != e["parent_id"]
                        and edge_key not in seen_edges):
                    seen_edges.add(edge_key)
                    links.append({
                        "source": e["child_id"],
                        "target": e["parent_id"],
                        "relation": e["relation"],
                        "color": _RELATION_COLORS.get(e["relation"], "#888"),
                        "confidence": e["confidence"],
                    })

        return {"nodes": nodes, "links": links}

    def subtree(self, root_id: str, max_depth: int = 5) -> dict:
        """Return subgraph reachable from root_id (children and grandchildren)."""
        all_data = self.to_d3()
        reachable: set[str] = {root_id}
        for _ in range(max_depth):
            added = False
            for link in all_data["links"]:
                if link["target"] in reachable and link["source"] not in reachable:
                    reachable.add(link["source"])
                    added = True
            if not added:
                break

        nodes = [n for n in all_data["nodes"] if n["id"] in reachable]
        links = [link for link in all_data["links"]
                 if link["source"] in reachable and link["target"] in reachable]
        return {"nodes": nodes, "links": links}
