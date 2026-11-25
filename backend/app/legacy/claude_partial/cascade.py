"""Cascading failure propagation over the dependency graph.

Rules (documented in docs/architecture.md):
* A dependent becomes AFFECTED when the weight share of its *hard* dependencies that are
  failed/affected reaches its `threshold` (default ~0: any single hard dependency).
* A dependency edge is MITIGATED when `mitigated_by` names a backup node that is not
  itself failed/affected. Mitigated edges transmit nothing (the backup carries the load).
* Soft failures, or hard failures below the threshold, make a node DEGRADED. Degraded
  nodes are reported but do not propagate further (conservative simplification).
* Propagation time = shortest sum of edge `delay_min` along triggering edges.
"""
import networkx as nx

FAILED_STATES = ("failed", "affected")


def propagate(G, roots):
    state, triggers, mitigated = {}, {}, []
    for r in roots:
        state[r] = "failed"
    for n in nx.topological_sort(G):
        if n in state:
            continue
        hard_total = hard_failed = soft_failed = 0.0
        trig = []
        for u, _v, e in G.in_edges(n, data=True):
            w = e.get("weight", 1.0)
            if e["kind"] == "hard":
                hard_total += w
            if state.get(u) not in FAILED_STATES:
                continue
            mit = e.get("mitigated_by")
            if mit and state.get(mit) not in FAILED_STATES and mit in G:
                mitigated.append({"edge": e["id"], "from": u, "to": n, "backup": mit,
                                  "note": e.get("description") or "Backup carries the dependency"})
                continue
            if e["kind"] == "hard":
                hard_failed += w
                trig.append(u)
            else:
                soft_failed += w
                trig.append(u)
        thr = G.nodes[n].get("threshold", 0.001) or 0.001
        if hard_total and hard_failed > 0 and hard_failed / hard_total >= thr - 1e-9:
            state[n] = "affected"
            triggers[n] = trig
        elif hard_failed > 0 or soft_failed > 0:
            state[n] = "degraded"
            triggers[n] = trig
    # propagation timing (minutes) over triggering edges
    t = {r: 0 for r in roots}
    for n in nx.topological_sort(G):
        if n in roots or state.get(n) not in FAILED_STATES + ("degraded",):
            continue
        cands = [t[u] + G.edges[(u, n)].get("delay_min", 0) for u in triggers.get(n, []) if u in t]
        if cands:
            t[n] = min(cands)
    return state, triggers, mitigated, t


def critical_chain(G, roots, state, triggers):
    """Highest-criticality failure path from a root to an affected operation/population."""
    best = {}
    for n in nx.topological_sort(G):
        if state.get(n) not in FAILED_STATES:
            continue
        if n in roots:
            best[n] = (G.nodes[n]["criticality"], [n])
            continue
        opts = [best[u] for u in triggers.get(n, []) if u in best and state.get(u) in FAILED_STATES]
        if opts:
            sc, path = max(opts, key=lambda x: (x[0], len(x[1])))
            best[n] = (sc + G.nodes[n]["criticality"], path + [n])
    ends = [n for n in best if G.nodes[n]["type"] in ("operation", "population") and n not in roots]
    if not ends: