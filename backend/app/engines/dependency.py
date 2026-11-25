import networkx as nx

from app.models.models import CampusNode, Dependency, Resource, RecoveryOption, Hostel


AVAILABLE = {"operational", "restored"}
FAILED = {"failed", "affected"}


def build_graph(db):
    graph = nx.DiGraph()
    nodes = db.query(CampusNode).all()
    resources = {resource.node_id: resource for resource in db.query(Resource).all()}
    for node in nodes:
        graph.add_node(
            node.id, name=node.name, type=node.node_type, status=node.status,
            criticality=node.criticality, criticality_label=node.criticality_label,
        )
    for edge in db.query(Dependency).all():
        graph.add_edge(
            edge.source_node_id, edge.target_node_id, id=edge.id, kind=edge.dependency_type,
            weight=edge.weight, mitigation_resource_id=edge.mitigation_resource_id,
        )
    if not nx.is_directed_acyclic_graph(graph):
        cycle = nx.find_cycle(graph)
        raise ValueError(f"Campus dependencies contain a cycle: {cycle}")
    return graph, resources


def _backup_capacity(db, source_id, backup_id, target, duration_minutes):
    backup = db.get(Resource, backup_id)
    if backup is None or backup.node is None or backup.node.status not in AVAILABLE:
        return "unavailable"
    if not backup.backup_available:
        return "unavailable"

    options = db.query(RecoveryOption).filter(
        RecoveryOption.required_resource_id == backup_id
    ).all()
    limits = " ".join(option.capacity_limit.lower() for option in options)
    if "priority_loads_only" in limits and target.get("criticality", 0) < 0.8:
        return "partial"
    if "finite_storage_hours" in limits:
        source = db.get(Resource, source_id)
        zone = source.zone_id if source else ""
        hostels = db.query(Hostel).filter(Hostel.water_zone == zone).all() if zone else []
        if not hostels:
            hostels = db.query(Hostel).all()
        hours = min((hostel.backup_hours for hostel in hostels), default=0)
        if duration_minutes > hours * 60:
            return "exceeded"
    if "60_percent_normal_traffic" in limits:
        return "partial"
    return "available"


def propagate(db, root_ids, duration_minutes=0):
    graph, resources = build_graph(db)
    roots = set(root_ids)
    missing = roots - set(graph.nodes)
    if missing:
        raise ValueError(f"Unknown campus node(s): {', '.join(sorted(missing))}")

    state = {
        node: (
            graph.nodes[node]["status"]
            if graph.nodes[node]["status"] in FAILED | {"degraded"}
            else "operational"
        )
        for node in graph.nodes
    }
    triggers, mitigated, waves = {}, [], {}
    active_roots = roots | {node for node, status in state.items() if status == "failed"}
    for root in active_roots:
        state[root] = "failed"
        waves[root] = 0

    for node in nx.topological_sort(graph):
        if node in active_roots:
            continue
        hard_failed, soft_failed, degraded_dependencies, trigger_nodes = [], [], [], []
        partial_backup = False
        for source, _, edge in graph.in_edges(node, data=True):
            source_state = state[source]
            if source_state not in FAILED | {"degraded"}:
                continue
            backup_id = edge.get("mitigation_resource_id")
            backup_state = _backup_capacity(
                db, source, backup_id, graph.nodes[node], duration_minutes
            ) if source_state in FAILED and backup_id else "unavailable"
            if backup_state == "available":
                mitigated.append({
                    "edge": edge["id"], "from": source, "to": node,
                    "backup": backup_id, "status": "mitigated",
                })
                continue
            if backup_state == "partial":
                partial_backup = True
                mitigated.append({
                    "edge": edge["id"], "from": source, "to": node,
                    "backup": backup_id, "status": "partial",
                })
                continue
            trigger_nodes.append(source)
            if source_state in FAILED:
                (hard_failed if edge["kind"] == "hard" else soft_failed).append(source)
            else:
                degraded_dependencies.append(source)

        if hard_failed:
            state[node] = "affected"
        elif soft_failed or partial_backup or degraded_dependencies:
            state[node] = "degraded"
        if state[node] != "operational":
            triggers[node] = trigger_nodes
            waves[node] = min((waves.get(source, 0) + 1 for source in trigger_nodes), default=1)

    return graph, resources, state, triggers, mitigated, waves


def critical_chain(graph, roots, state, triggers):
    best = {}
    for node in nx.topological_sort(graph):
        if state.get(node) not in FAILED:
            continue
        if node in roots:
            best[node] = (graph.nodes[node]["criticality"], [node])
            continue
        candidates = [
            best[source] for source in triggers.get(node, [])
            if source in best and state.get(source) in FAILED
        ]
        if candidates:
            score, path = max(candidates, key=lambda item: (item[0], len(item[1])))
            best[node] = (score + graph.nodes[node]["criticality"], path + [node])
    endpoints = [
        node for node in best
        if graph.nodes[node]["type"] == "service" and node not in roots
    ]
    candidates = [best[node][1] for node in endpoints]
    if not candidates:
        candidates = [best[node][1] for node in roots if node in best]
    return max(candidates, key=len, default=[])
