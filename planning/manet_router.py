"""OLSR MANET routing protocol simulation."""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple
import networkx as nx
import numpy as np
from utils.logger import get_logger
log = get_logger("MANET")


@dataclass
class MANETNode:
    node_id: str
    lat: float
    lon: float
    radio_range_m: float = 5000.0
    status: str = "UP"
    neighbors: Set[str] = field(default_factory=set)
    mpr_set: Set[str] = field(default_factory=set)
    routing_table: Dict[str, str] = field(default_factory=dict)


class MANETRouter:
    """OLSR (Optimized Link State Routing) MANET simulation."""

    def __init__(self, hello_interval_s=2.0, tc_interval_s=5.0):
        self.hello_interval = hello_interval_s
        self.tc_interval = tc_interval_s
        self.nodes: Dict[str, MANETNode] = {}
        self.graph = nx.Graph()
        self._link_quality: Dict[Tuple[str,str], float] = {}

    def add_node(self, node_id: str, lat: float, lon: float, range_m: float = 5000.0):
        node = MANETNode(node_id=node_id, lat=lat, lon=lon, radio_range_m=range_m)
        self.nodes[node_id] = node
        self.graph.add_node(node_id, lat=lat, lon=lon)

    def _distance(self, n1: MANETNode, n2: MANETNode) -> float:
        R = 6371000
        p1, p2 = np.radians(n1.lat), np.radians(n2.lat)
        dp = np.radians(n2.lat - n1.lat)
        dl = np.radians(n2.lon - n1.lon)
        a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

    def discover_neighbors(self):
        for nid, node in self.nodes.items():
            node.neighbors.clear()
        self.graph.clear()
        for nid, node in self.nodes.items():
            self.graph.add_node(nid, lat=node.lat, lon=node.lon)
        for nid1, n1 in self.nodes.items():
            for nid2, n2 in self.nodes.items():
                if nid1 >= nid2:
                    continue
                dist = self._distance(n1, n2)
                min_range = min(n1.radio_range_m, n2.radio_range_m)
                if dist <= min_range and n1.status == "UP" and n2.status == "UP":
                    n1.neighbors.add(nid2)
                    n2.neighbors.add(nid1)
                    quality = max(0.1, 1.0 - dist / min_range)
                    self._link_quality[(nid1, nid2)] = quality
                    self._link_quality[(nid2, nid1)] = quality
                    self.graph.add_edge(nid1, nid2, weight=1.0/quality, distance=dist)

    def compute_mpr(self):
        for nid, node in self.nodes.items():
            two_hop = set()
            for nbr_id in node.neighbors:
                nbr = self.nodes.get(nbr_id)
                if nbr:
                    two_hop.update(nbr.neighbors - {nid} - node.neighbors)
            mpr = set()
            covered = set()
            while two_hop - covered:
                best = max(node.neighbors - mpr,
                           key=lambda n: len(self.nodes[n].neighbors & (two_hop - covered))
                           if n in self.nodes else 0, default=None)
                if best is None:
                    break
                mpr.add(best)
                covered.update(self.nodes[best].neighbors & two_hop)
            node.mpr_set = mpr

    def compute_routing_tables(self):
        self.discover_neighbors()
        self.compute_mpr()
        for nid in self.nodes:
            node = self.nodes[nid]
            node.routing_table.clear()
            try:
                paths = nx.single_source_dijkstra_path(self.graph, nid, weight="weight")
                for dest, path in paths.items():
                    if len(path) >= 2:
                        node.routing_table[dest] = path[1]
            except nx.NetworkXError:
                pass

    def get_route(self, src: str, dst: str) -> List[str]:
        try:
            return nx.shortest_path(self.graph, src, dst, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_link_quality(self, n1: str, n2: str) -> float:
        return self._link_quality.get((n1, n2), 0.0)

    def get_connectivity_matrix(self) -> Dict:
        nodes = sorted(self.nodes.keys())
        matrix = {}
        for n in nodes:
            matrix[n] = {m: self.get_link_quality(n, m) for m in nodes}
        return matrix

    def simulate_node_failure(self, node_id: str):
        if node_id in self.nodes:
            self.nodes[node_id].status = "DOWN"
            self.compute_routing_tables()

    def get_network_stats(self) -> Dict:
        up_nodes = [n for n in self.nodes.values() if n.status == "UP"]
        return {
            "total_nodes": len(self.nodes),
            "up_nodes": len(up_nodes),
            "edges": self.graph.number_of_edges(),
            "connected": nx.is_connected(self.graph) if self.graph.number_of_nodes() > 0 else False,
            "avg_neighbors": np.mean([len(n.neighbors) for n in up_nodes]) if up_nodes else 0,
        }


if __name__ == "__main__":
    router = MANETRouter()
    units = [("B01",34.05,-117.45),("B02",34.07,-117.42),("B03",34.10,-117.38),
             ("B04",34.12,-117.35),("B05",34.15,-117.30)]
    for uid, lat, lon in units:
        router.add_node(uid, lat, lon, range_m=8000)
    router.compute_routing_tables()
    route = router.get_route("B01", "B05")
    print(f"Route B01→B05: {route}")
    print(f"Network: {router.get_network_stats()}")
    print("manet_router.py OK")
