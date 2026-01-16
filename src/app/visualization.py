"""
Advanced Visualization Module
Provides 3D graphs, heatmaps, and real-time analytics visualization
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class Visualization3D:
    """3D network graph visualization"""

    def __init__(self, title: str = "Network Topology"):
        self.title = title
        self.nodes = []
        self.edges = []
        self.metadata = {"created_at": datetime.utcnow().isoformat()}

    def add_node(
        self,
        id: str,
        label: str,
        node_type: str = "default",
        size: float = 1.0,
        color: str = "#1f77b4",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add node to 3D graph"""
        node = {
            "id": id,
            "label": label,
            "type": node_type,
            "size": size,
            "color": color,
            "metadata": metadata or {},
            "position": {"x": 0, "y": 0, "z": 0},  # Auto-layout
        }
        self.nodes.append(node)

    def add_edge(
        self,
        source: str,
        target: str,
        weight: float = 1.0,
        edge_type: str = "default",
        color: str = "#666666",
    ):
        """Add edge to 3D graph"""
        edge = {
            "source": source,
            "target": target,
            "weight": weight,
            "type": edge_type,
            "color": color,
        }
        self.edges.append(edge)

    def to_three_js(self) -> Dict[str, Any]:
        """Convert to Three.js compatible format"""
        geometry = {"vertices": [], "faces": []}

        # Build geometry from nodes and edges
        for i, node in enumerate(self.nodes):
            geometry["vertices"].append(
                [node["position"]["x"], node["position"]["y"], node["position"]["z"]]
            )

        for edge in self.edges:
            source_idx = next(
                (i for i, n in enumerate(self.nodes) if n["id"] == edge["source"]),
                None,
            )
            target_idx = next(
                (i for i, n in enumerate(self.nodes) if n["id"] == edge["target"]),
                None,
            )
            if source_idx is not None and target_idx is not None:
                geometry["faces"].append([source_idx, target_idx])

        return {
            "title": self.title,
            "geometry": geometry,
            "nodes": self.nodes,
            "edges": self.edges,
        }

    def to_json(self) -> str:
        """Export as JSON"""
        return json.dumps(
            {
                "title": self.title,
                "nodes": self.nodes,
                "edges": self.edges,
                "metadata": self.metadata,
            }
        )


class Heatmap:
    """Heatmap visualization for time-series data"""

    def __init__(self, title: str = "Analytics Heatmap"):
        self.title = title
        self.data = []
        self.x_axis = []  # Time
        self.y_axis = []  # Categories
        self.color_scale = "YlOrRd"  # Yellow-Orange-Red

    def add_data_point(
        self,
        x: str,  # Time
        y: str,  # Category
        value: float,
    ):
        """Add data point to heatmap"""
        self.data.append({"x": x, "y": y, "value": value})

        if x not in self.x_axis:
            self.x_axis.append(x)
        if y not in self.y_axis:
            self.y_axis.append(y)

    def get_matrix(self) -> List[List[float]]:
        """Get heatmap matrix"""
        matrix = [[0.0 for _ in self.x_axis] for _ in self.y_axis]

        for point in self.data:
            x_idx = self.x_axis.index(point["x"])
            y_idx = self.y_axis.index(point["y"])
            matrix[y_idx][x_idx] = point["value"]

        return matrix

    def to_plotly(self) -> Dict[str, Any]:
        """Convert to Plotly compatible format"""
        matrix = self.get_matrix()

        return {
            "type": "heatmap",
            "z": matrix,
            "x": self.x_axis,
            "y": self.y_axis,
            "colorscale": self.color_scale,
            "title": self.title,
        }


class TimeSeriesChart:
    """Time-series chart visualization"""

    def __init__(self, title: str = "Time Series"):
        self.title = title
        self.series = {}
        self.timestamps = []

    def add_series(self, name: str, data: List[float], color: str = None):
        """Add time series"""
        self.series[name] = {"data": data, "color": color or "#1f77b4"}

    def set_timestamps(self, timestamps: List[str]):
        """Set x-axis timestamps"""
        self.timestamps = timestamps

    def to_chart_js(self) -> Dict[str, Any]:
        """Convert to Chart.js compatible format"""
        datasets = []
        colors = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
        ]

        for i, (name, series) in enumerate(self.series.items()):
            datasets.append(
                {
                    "label": name,
                    "data": series["data"],
                    "borderColor": series.get("color", colors[i % len(colors)]),
                    "tension": 0.3,
                    "fill": False,
                }
            )

        return {
            "type": "line",
            "data": {
                "labels": self.timestamps,
                "datasets": datasets,
            },
            "options": {
                "responsive": True,
                "plugins": {"title": {"display": True, "text": self.title}},
                "scales": {
                    "y": {"beginAtZero": True},
                },
            },
        }


class PredictiveChart:
    """Predictive analytics visualization"""

    def __init__(self, title: str = "Predictive Analysis"):
        self.title = title
        self.historical_data = []
        self.predicted_data = []
        self.confidence_interval = []

    def add_historical_point(self, timestamp: str, value: float):
        """Add historical data point"""
        self.historical_data.append({"timestamp": timestamp, "value": value})

    def add_prediction(
        self,
        timestamp: str,
        predicted_value: float,
        lower_bound: float,
        upper_bound: float,
    ):
        """Add prediction with confidence interval"""
        self.predicted_data.append(
            {"timestamp": timestamp, "value": predicted_value}
        )
        self.confidence_interval.append(
            {
                "timestamp": timestamp,
                "lower": lower_bound,
                "upper": upper_bound,
            }
        )

    def to_plotly(self) -> Dict[str, Any]:
        """Convert to Plotly compatible format"""
        traces = []

        # Historical data
        if self.historical_data:
            historical_timestamps = [d["timestamp"] for d in self.historical_data]
            historical_values = [d["value"] for d in self.historical_data]

            traces.append(
                {
                    "name": "Historical",
                    "x": historical_timestamps,
                    "y": historical_values,
                    "type": "scatter",
                    "mode": "lines",
                    "line": {"color": "blue"},
                }
            )

        # Predictions
        if self.predicted_data:
            pred_timestamps = [d["timestamp"] for d in self.predicted_data]
            pred_values = [d["value"] for d in self.predicted_data]

            traces.append(
                {
                    "name": "Predicted",
                    "x": pred_timestamps,
                    "y": pred_values,
                    "type": "scatter",
                    "mode": "lines",
                    "line": {"color": "orange", "dash": "dash"},
                }
            )

        # Confidence interval
        if self.confidence_interval:
            ci_timestamps = [c["timestamp"] for c in self.confidence_interval]
            ci_lower = [c["lower"] for c in self.confidence_interval]
            ci_upper = [c["upper"] for c in self.confidence_interval]

            traces.append(
                {
                    "name": "Confidence Interval",
                    "x": ci_timestamps + ci_timestamps[::-1],
                    "y": ci_upper + ci_lower[::-1],
                    "type": "scatter",
                    "fill": "toself",
                    "fillcolor": "rgba(0,100,200,0.2)",
                    "line": {"color": "transparent"},
                    "showlegend": True,
                }
            )

        return {
            "data": traces,
            "layout": {
                "title": self.title,
                "xaxis": {"title": "Time"},
                "yaxis": {"title": "Value"},
                "hovermode": "x unified",
            },
        }


class VisualizationDashboard:
    """Complete visualization dashboard"""

    def __init__(self, title: str = "Analytics Dashboard"):
        self.title = title
        self.widgets = {}
        self.created_at = datetime.utcnow()

    def add_widget(
        self,
        widget_id: str,
        widget_type: str,
        title: str,
        position: Dict[str, int],
    ):
        """Add widget to dashboard"""
        self.widgets[widget_id] = {
            "type": widget_type,
            "title": title,
            "position": position,
            "data": None,
        }

    def update_widget_data(self, widget_id: str, data: Any):
        """Update widget data"""
        if widget_id in self.widgets:
            self.widgets[widget_id]["data"] = data

    def get_layout(self) -> Dict[str, Any]:
        """Get dashboard layout"""
        return {
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "widgets": self.widgets,
            "grid": {
                "cols": 12,
                "rows": len(self.widgets),
            },
        }

    def to_json(self) -> str:
        """Export dashboard as JSON"""
        return json.dumps(self.get_layout())


class RealTimeVisualization:
    """Real-time data visualization with WebSocket support"""

    def __init__(self):
        self.update_buffer = []
        self.last_update = datetime.utcnow()
        self.update_interval_ms = 1000  # Update every 1 second

    def add_update(self, data: Dict[str, Any]):
        """Add data to update buffer"""
        self.update_buffer.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "data": data,
            }
        )

    def get_updates(self, since_timestamp: Optional[datetime] = None) -> List[Dict]:
        """Get buffered updates"""
        if not since_timestamp:
            return self.update_buffer

        return [
            update
            for update in self.update_buffer
            if datetime.fromisoformat(update["timestamp"]) >= since_timestamp
        ]

    def clear_buffer(self):
        """Clear update buffer"""
        self.update_buffer = []
        self.last_update = datetime.utcnow()


def create_visualization_config() -> Dict[str, Any]:
    """Create visualization configuration"""
    return {
        "visualization": {
            "enabled": True,
            "update_interval_ms": 1000,
            "libraries": {
                "3d_graphs": {
                    "enabled": True,
                    "library": "three.js",
                    "version": "r128",
                },
                "heatmaps": {
                    "enabled": True,
                    "library": "plotly.js",
                    "colorscale": "YlOrRd",
                },
                "time_series": {
                    "enabled": True,
                    "library": "chart.js",
                    "version": "3.9.1",
                },
                "real_time": {
                    "enabled": True,
                    "websocket": True,
                    "buffer_size": 1000,
                },
            },
            "themes": {
                "default": "light",
                "options": ["light", "dark", "high_contrast"],
            },
        }
    }
