"""Network fraud detection using graph analysis"""

import logging
from typing import Dict, List, Set, Tuple, Any
from datetime import datetime, timedelta
import networkx as nx
from collections import defaultdict
import joblib
from pathlib import Path

logger = logging.getLogger(__name__)

MODEL_DIR = Path("models")
MODEL_DIR.mkdir(exist_ok=True)


class NetworkFraudDetector:
    """Detect fraud rings and suspicious network patterns"""
    
    def __init__(self):
        self.graph = nx.Graph()
        self.device_connections: Dict[str, Set[str]] = defaultdict(set)
        self.ip_connections: Dict[str, Set[str]] = defaultdict(set)
        self.payment_connections: Dict[str, Set[str]] = defaultdict(set)
        self.fraud_rings: List[Set[str]] = []
        self.model_path = MODEL_DIR / "network_fraud.pkl"
        self.load_model()
    
    def add_user_event(
        self,
        user_id: str,
        device_id: str = None,
        ip_address: str = None,
        payment_method: str = None
    ) -> None:
        """Add user event to network for fraud detection"""
        
        if not self.graph.has_node(user_id):
            self.graph.add_node(user_id, type="user")
        
        # Add device connections
        if device_id:
            self.device_connections[device_id].add(user_id)
            edge_id = f"device:{device_id}"
            if not self.graph.has_node(edge_id):
                self.graph.add_node(edge_id, type="device")
            self.graph.add_edge(user_id, edge_id, connection_type="device")
        
        # Add IP connections
        if ip_address:
            self.ip_connections[ip_address].add(user_id)
            edge_id = f"ip:{ip_address}"
            if not self.graph.has_node(edge_id):
                self.graph.add_node(edge_id, type="ip")
            self.graph.add_edge(user_id, edge_id, connection_type="ip")
        
        # Add payment method connections
        if payment_method:
            self.payment_connections[payment_method].add(user_id)
            edge_id = f"payment:{payment_method}"
            if not self.graph.has_node(edge_id):
                self.graph.add_node(edge_id, type="payment")
            self.graph.add_edge(user_id, edge_id, connection_type="payment")
    
    def detect_fraud_rings(
        self,
        min_ring_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Detect fraud rings (cliques of connected users).
        Users sharing multiple attributes (device, IP, payment) with 5+ other users.
        """
        fraud_rings = []
        
        # Check device-sharing rings
        for device_id, users in self.device_connections.items():
            if len(users) >= min_ring_size:
                fraud_rings.append({
                    "ring_type": "device_sharing",
                    "connection": device_id,
                    "users": list(users),
                    "size": len(users),
                    "risk_score": min(1.0, (len(users) - min_ring_size) / 10),
                })
        
        # Check IP-sharing rings
        for ip_addr, users in self.ip_connections.items():
            if len(users) >= min_ring_size:
                fraud_rings.append({
                    "ring_type": "ip_sharing",
                    "connection": ip_addr,
                    "users": list(users),
                    "size": len(users),
                    "risk_score": min(1.0, (len(users) - min_ring_size) / 10),
                })
        
        # Check payment method rings
        for payment_id, users in self.payment_connections.items():
            if len(users) >= min_ring_size:
                fraud_rings.append({
                    "ring_type": "payment_sharing",
                    "connection": payment_id,
                    "users": list(users),
                    "size": len(users),
                    "risk_score": min(1.0, (len(users) - min_ring_size) / 10),
                })
        
        self.fraud_rings = [ring["users"] for ring in fraud_rings]
        return fraud_rings
    
    def get_user_network_risk(
        self,
        user_id: str,
        max_hops: int = 2
    ) -> Dict[str, Any]:
        """
        Calculate risk score based on user's position in network.
        Users connected to known fraud patterns are higher risk.
        """
        if user_id not in self.graph:
            return {
                "risk_score": 0.0,
                "risk_factors": [],
                "connected_suspicious_users": [],
            }
        
        risk_factors = []
        connected_suspicious = []
        risk_score = 0.0
        
        # Get neighbors up to max_hops
        neighbors = set(nx.ego_graph(self.graph, user_id, radius=max_hops).nodes())
        neighbors.discard(user_id)
        
        # Check if user is in a fraud ring
        for ring in self.fraud_rings:
            if user_id in ring:
                risk_factors.append("member_of_fraud_ring")
                risk_score += 0.8
                break
        
        # Count connections to other suspicious users
        for neighbor in neighbors:
            if neighbor.startswith("device:") or neighbor.startswith("ip:"):
                # Get all users connected to this device/IP
                if self.graph.has_node(neighbor):
                    neighbors_of_neighbor = list(self.graph.neighbors(neighbor))
                    for nnn in neighbors_of_neighbor:
                        if not nnn.startswith(("device:", "ip:", "payment:")):
                            connected_suspicious.append(nnn)
        
        # High degree centrality indicates central position in network
        try:
            centrality = nx.degree_centrality(self.graph).get(user_id, 0)
            if centrality > 0.1:  # In top 10% of connected users
                risk_factors.append("high_network_centrality")
                risk_score += centrality * 0.3
        except:
            pass
        
        # Check clustering coefficient (how connected are neighbors to each other)
        try:
            if user_id in self.graph:
                clustering = nx.clustering(self.graph, user_id)
                if clustering > 0.5:  # Users connected to this user are highly connected
                    risk_factors.append("high_network_clustering")
                    risk_score += 0.2
        except:
            pass
        
        # Normalize risk score
        risk_score = min(1.0, risk_score)
        
        return {
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "connected_suspicious_users": list(set(connected_suspicious))[:10],
        }
    
    def get_network_statistics(self) -> Dict[str, Any]:
        """Get network topology statistics"""
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "number_of_components": nx.number_connected_components(self.graph),
            "average_degree": 0,
            "detected_fraud_rings": len(self.fraud_rings),
            "users_in_fraud_rings": sum(len(ring) for ring in self.fraud_rings),
        }
        
        if self.graph.number_of_nodes() > 0:
            degrees = [d for n, d in self.graph.degree()]
            stats["average_degree"] = sum(degrees) / len(degrees) if degrees else 0
        
        return stats
    
    def clear_old_connections(self, days: int = 30) -> None:
        """Clear connections older than specified days"""
        # This is a placeholder - in real implementation,
        # would track timestamps on edges and remove old ones
        pass
    
    def save_model(self) -> None:
        """Save network graph to disk"""
        try:
            data = {
                "graph": self.graph,
                "fraud_rings": self.fraud_rings,
                "device_connections": dict(self.device_connections),
                "ip_connections": dict(self.ip_connections),
                "payment_connections": dict(self.payment_connections),
            }
            joblib.dump(data, self.model_path)
            logger.info("Network fraud model saved")
        except Exception as e:
            logger.error(f"Failed to save network fraud model: {e}")
    
    def load_model(self) -> None:
        """Load network graph from disk"""
        try:
            if self.model_path.exists():
                data = joblib.load(self.model_path)
                self.graph = data.get("graph", nx.Graph())
                self.fraud_rings = data.get("fraud_rings", [])
                self.device_connections = defaultdict(
                    set, data.get("device_connections", {})
                )
                self.ip_connections = defaultdict(
                    set, data.get("ip_connections", {})
                )
                self.payment_connections = defaultdict(
                    set, data.get("payment_connections", {})
                )
                logger.info("Network fraud model loaded")
        except Exception as e:
            logger.warning(f"Could not load network fraud model: {e}")


# Global instance
network_fraud_detector = NetworkFraudDetector()
