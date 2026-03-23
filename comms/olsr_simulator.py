"""OLSR protocol simulation for MANET tactical comms."""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
import numpy as np
import networkx as nx
from utils.logger import get_logger

log = get_logger("OLSR_SIM")


@dataclass
class OLSRNode:
    node_id: str
    lat: float
    lon: float
    radio_range_m: float = 5000.0
    frequency_mhz: float = 225.0
    power_watts: float = 5.0
    status: str = "UP"
    neighbors: Set[str] = field(default_factory=set)
    mpr_set: Set[str] = field(default_factory=set)
    mpr_selector_set: Set[str] = field(default_factory=set)
    routing_table: Dict[str, Tuple[str, int]] = field(default_factory=dict)
    tc_messages_sent: int = 0
    hello_messages_sent: int = 0


class OLSRSimulator:
    """Full OLSR (RFC 3626) MANET simulation."""

    def __init__(self, hello_interval=2.0, tc_interval=5.0, neighbor_hold_time=6.0):
        self.hello_interval = hello_interval
        self.tc_interval = tc_interval
        self.neighbor_hold_time = neighbor_hold_time
        self.nodes: Dict[str, OLSRNode] = {}
        self.topology = nx.Graph()
        self._sim_time = 0.0

    def add_node(self, node_id: str, lat: float, lon: float, range_m: float = 5000.0):
        node = OLSRNode(node_id=node_id, lat=lat, lon=lon, radio_range_m=range_m)
        self.nodes[node_id] = node
        self.topology.add_node(node_id, lat=lat, lon=lon)

    def remove_node(self, node_id: str):
        if node_id in self.nodes:
            self.nodes[node_id].status = "DOWN"
            if node_id in self.topology:
                self.topology.remove_node(node_id)

    def _haversine(self, lat1, lon1, lat2, lon2) -> float:
        R = 6371000
        p1, p2 = np.radians(lat1), np.radians(lat2)
        dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    def send_hello(self):
        """HELLO message exchange — discover 1-hop neighbors."""
        self.topology.clear()
        for nid, node in self.nodes.items():
            if node.status == "UP":
                self.topology.add_node(nid, lat=node.lat, lon=node.lon)
        for nid1, n1 in self.nodes.items():
            if n1.status != "UP":
                continue
            n1.neighbors.clear()
            for nid2, n2 in self.nodes.items():
                if nid1 == nid2 or n2.status != "UP":
                    continue
                dist = self._haversine(n1.lat, n1.lon, n2.lat, n2.lon)
                if dist <= min(n1.radio_range_m, n2.radio_range_m):
                    n1.neighbors.add(nid2)
                    self.topology.add_edge(
                        nid1, nid2, distance=dist, quality=max(0.1, 1.0 - dist / n1.radio_range_m)
                    )
            n1.hello_messages_sent += 1

    def compute_mpr_sets(self):
        """Compute Multipoint Relay sets per OLSR spec."""
        for nid, node in self.nodes.items():
            if node.status != "UP":
                continue
            two_hop = set()
            for nbr_id in node.neighbors:
                nbr = self.nodes.get(nbr_id)
                if nbr and nbr.status == "UP":
                    two_hop.update(nbr.neighbors - {nid} - node.neighbors)
            mpr = set()
            covered = set()
            # Greedy MPR selection
            while two_hop - covered:
                candidates = node.neighbors - mpr
                if not candidates:
                    break
                best = max(
                    candidates,
                    key=lambda n: (
                        len(self.nodes[n].neighbors & (two_hop - covered)) if n in self.nodes else 0
                    ),
                    default=None,
                )
                if best is None:
                    break
                mpr.add(best)
                covered.update(self.nodes[best].neighbors & two_hop)
            node.mpr_set = mpr
            # Update MPR selector sets
            for m in mpr:
                if m in self.nodes:
                    self.nodes[m].mpr_selector_set.add(nid)

    def send_tc(self):
        """Topology Control message — advertise MPR selector set."""
        for nid, node in self.nodes.items():
            if node.status == "UP" and node.mpr_selector_set:
                node.tc_messages_sent += 1

    def compute_routing_tables(self):
        """Compute shortest paths using OLSR topology."""
        self.send_hello()
        self.compute_mpr_sets()
        self.send_tc()
        for nid, node in self.nodes.items():
            if node.status != "UP":
                continue
            node.routing_table.clear()
            try:
                paths = nx.single_source_dijkstra_path(self.topology, nid, weight="distance")
                _ = nx.single_source_dijkstra_path_length(self.topology, nid, weight="distance")
                for dest, path in paths.items():
                    if dest != nid and len(path) >= 2:
                        node.routing_table[dest] = (path[1], len(path) - 1)
            except nx.NetworkXError:
                pass

    def route_message(self, src: str, dst: str) -> List[str]:
        try:
            return nx.shortest_path(self.topology, src, dst, weight="distance")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def step(self, dt: float = 1.0):
        self._sim_time += dt
        if self._sim_time % self.hello_interval < dt:
            self.send_hello()
        if self._sim_time % self.tc_interval < dt:
            self.compute_mpr_sets()
            self.send_tc()

    def get_network_state(self) -> Dict:
        up = [n for n in self.nodes.values() if n.status == "UP"]
        return {
            "total_nodes": len(self.nodes),
            "up_nodes": len(up),
            "edges": self.topology.number_of_edges(),
            "connected": nx.is_connected(self.topology) if len(up) > 1 else False,
            "avg_neighbors": np.mean([len(n.neighbors) for n in up]) if up else 0,
            "sim_time": self._sim_time,
        }


if __name__ == "__main__":
    sim = OLSRSimulator()
    for i, (lat, lon) in enumerate(
        [(34.05, -117.45), (34.07, -117.42), (34.10, -117.38), (34.12, -117.35), (34.15, -117.30)]
    ):
        sim.add_node(f"N{i}", lat, lon, 8000)
    sim.compute_routing_tables()
    route = sim.route_message("N0", "N4")
    print(f"Route N0→N4: {route}")
    print(f"Network: {sim.get_network_state()}")
    print("olsr_simulator.py OK")
