"""Dependency graph (NetworkX). Edge direction: provider -> dependent, so a failure
flows along the edges."""
import networkx as nx

STATUS_OK = "operational"


class DependencyEngine:
    def __init__(self, campus):
        self.campus = campus
        self.G = nx.DiGraph()
        for n in campus.nodes.values():
            self.G.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
        for e in campus.edges:
            if e["source"] in self.G and e["target"] in self.G:
                self.G.add_edge(e["source"], e["target"], **{k: v for k, v in e.items() if k not in ("source", "target")})
        if not nx.is_directed_acyclic_graph(self.G):
            cyc = nx.find_cycle(self.G)
            raise ValueError(f"Dependency graph must be acyclic; found cycle {cyc}")

    # ---- queries ------------------------------------------------------
    def direct_dependents(self, node_id):
        return sorted(self.G.successors(node_id))

    def direct_dependencies(self, node_id):
        return sorted(self.G.predecessors(node_id))

    def all_dependents(self, node_id):
        """Every node that could be affected if node_id fails (structural, ignores redundancy)."""
        return sorted(nx.descendants(self.G, node_id))

    def all_dependencies(self, node_id):
        return sorted(nx.ancestors(self.G, node_id))

    def describe(self, node_id):
        n = self.G.nodes[node_id]
        return {
            "id": node_id, "name": n["name"], "type": n["type"], "status": n["status"],
            "direct_dependencies": [self._brief(x, node_id, True) for x in self.direct_dependencies(node_id)],
            "direct_dependents": [self._brief(x, node_id, False) for x in self.direct_dependents(node_id)],
            "indirect_dependents": [self._brief(x) for x in self.all_dependents(node_id) if x not in self.G.successors(node_id)],
            "indirect_dependencies": [self._brief(x) for x in self.all_dependencies(node_id) if x not in self.G.predecessors(node_id)],
            "total_dependents": len(nx.descendants(self.G, node_id)),
            "total_dependencies": len(nx.ancestors(self.G, node_id)),
        }

    def _brief(self, nid, other=None, upstream=False):
        d = {"id": nid, "name": self.G.nodes[nid]["name"], "type": self.G.nodes[nid]["type"]}
        if other:
            e = self.G.edges[(nid, other)] if upstream else self.G.edges[(other, nid)]
            d.update({"edge_kind": e["kind"], "mitigated_by": e.get("mitigated_by")})
        return d

    # ---- layout -------------------------------------------------------
    def layers(self):
        out = {}
        for gen, nodes in enumerate(nx.topological_generations(self.G)):
            for n in nodes:
                out[n] = gen
        return out

    def payload(self, include_faculty=False, include_students=False):
        layers = self.layers()
        hidden = set() if include_faculty else {n for n, d in self.G.nodes(data=True) if d["type"] == "faculty"}
        # compact: faculty nodes sit in layer 0 anyway when shown
        by_layer = {}
        for n in nx.topological_sort(self.G):
            if n in hidden:
                continue
            by_layer.setdefault(layers[n], []).append(n)
        nodes = []