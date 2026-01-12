import logging
import asyncio
from .queue import event_queue
from .kafka_config import kafka_settings

logger = logging.getLogger(__name__)


async def process_events():
    """백그라운드 이벤트 처리"""
    
    async def event_callback(event: dict):
        """각 이벤트 처리"""
        logger.info(f"처리 중: {event['event_type']} - {event['user_id']}")
        
        # 여기서 ML 리스크 엔진 실행
        # anomaly_score = detect_anomaly(event)
        # if anomaly_score > threshold:
        #     await event_queue.enqueue_anomaly({...})
        
        await asyncio.sleep(0.1)  # 처리 시뮬레이션
    
    if event_queue.use_kafka:
        await event_queue.subscribe_to_events(event_callback)
    else:
        logger.warning("Kafka 사용 불가 - 로컬 메모리 큐 사용 중")
