"""
WebSocket Real-time Streaming Module
Provides real-time event streaming and dashboard updates via WebSocket
"""

from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from typing import Set, Dict, Any
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and broadcasts"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.client_subscriptions: Dict[WebSocket, Set[str]] = {}

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        self.client_subscriptions[websocket] = {"all"}  # Default subscription
        logger.info(f"Client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket"""
        self.active_connections.discard(websocket)
        self.client_subscriptions.pop(websocket, None)
        logger.info(f"Client disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any], event_type: str = "all"):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        disconnected = set()
        for connection in self.active_connections:
            try:
                # Check if client subscribed to this event type
                subscriptions = self.client_subscriptions.get(connection, {"all"})
                if event_type in subscriptions or "all" in subscriptions:
                    await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_personal(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time event streaming"""
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle different message types
            if message.get("type") == "subscribe":
                event_types = message.get("events", ["all"])
                manager.client_subscriptions[websocket] = set(event_types)
                await manager.send_personal(
                    websocket,
                    {
                        "type": "subscription_confirmed",
                        "events": event_types,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            elif message.get("type") == "ping":
                await manager.send_personal(
                    websocket,
                    {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )

            elif message.get("type") == "unsubscribe":
                event_types = message.get("events", [])
                current_subs = manager.client_subscriptions.get(websocket, {"all"})
                for event in event_types:
                    current_subs.discard(event)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


async def broadcast_event(
    event_type: str, event_data: Dict[str, Any], source: str = "system"
):
    """Broadcast event to all connected clients"""
    message = {
        "type": event_type,
        "source": source,
        "timestamp": datetime.utcnow().isoformat(),
        "data": event_data,
    }
    await manager.broadcast(message, event_type)


async def broadcast_metric_update(metric_name: str, metric_value: Any):
    """Broadcast metric update to all connected clients"""
    message = {
        "type": "metric_update",
        "metric": metric_name,
        "value": metric_value,
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(message, "metrics")


async def broadcast_alert(
    alert_level: str, message: str, details: Dict[str, Any] = None
):
    """Broadcast alert to all connected clients"""
    alert_message = {
        "type": "alert",
        "level": alert_level,  # critical, high, medium, low
        "message": message,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat(),
    }
    await manager.broadcast(alert_message, "alerts")


# Integration hooks for main app
def get_manager():
    """Get the global connection manager"""
    return manager
