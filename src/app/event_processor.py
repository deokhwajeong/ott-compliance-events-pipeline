import logging
import asyncio
from .queue import event_queue
from .kafka_config import kafka_settings

logger = logging.getLogger(__name__)


async def process_events():
    """Background event processing"""
    
    async def event_callback(event: dict):
        """Process individual event"""
        logger.info(f"Processing: {event['event_type']} - {event['user_id']}")
        
        # Run ML risk engine here
        # anomaly_score = detect_anomaly(event)
        # if anomaly_score > threshold:
        #     await event_queue.enqueue_anomaly({...})
        
        await asyncio.sleep(0.1)  # Simulate processing
    
    if event_queue.use_kafka:
        await event_queue.subscribe_to_events(event_callback)
    else:
        logger.warning("Kafka not available - using local memory queue")
