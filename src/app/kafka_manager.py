import json
import logging
from typing import Callable, Optional
from datetime import datetime
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError
from contextlib import asynccontextmanager
import asyncio

from .kafka_config import kafka_settings

logger = logging.getLogger(__name__)


class KafkaManager:
    """Kafka 프로듀서/컨슈머 관리"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.partitioner_map = {}  # 파티션 캐시
    
    async def init_producer(self):
        """Kafka 프로듀서 초기화"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=kafka_settings.bootstrap_servers,
            compression_type='snappy',
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka Producer 시작됨")
    
    async def init_consumer(self, topic: str, callback: Callable):
        """Kafka 컨슈머 초기화"""
        self.consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=kafka_settings.bootstrap_servers,
            group_id=kafka_settings.consumer_group,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        await self.consumer.start()
        logger.info(f"Kafka Consumer 시작됨: {topic}")
        
        # 메시지 처리
        try:
            async for message in self.consumer:
                await callback(message.value)
        except Exception as e:
            logger.error(f"컨슈머 에러: {e}")
        finally:
            await self.consumer.stop()
    
    async def send_event(self, topic: str, event: dict, partition_key: Optional[str] = None):
        """이벤트 발행"""
        if not self.producer:
            raise RuntimeError("Producer 초기화되지 않음")
        
        try:
            # 파티션 키: user_id 또는 device_id 기반 (샤딩)
            key = partition_key.encode('utf-8') if partition_key else None
            
            await self.producer.send_and_wait(
                topic,
                value=event,
                key=key,
                timestamp_ms=int(datetime.utcnow().timestamp() * 1000)
            )
            logger.debug(f"이벤트 발행됨 [{topic}]: {event}")
        except KafkaError as e:
            logger.error(f"발행 실패: {e}")
            raise
    
    async def batch_send(self, topic: str, events: list[dict], partition_key: Optional[str] = None):
        """배치 발행 (성능 최적화)"""
        if not self.producer:
            raise RuntimeError("Producer 초기화되지 않음")
        
        futures = []
        for event in events:
            key = partition_key.encode('utf-8') if partition_key else None
            future = self.producer.send(topic, value=event, key=key)
            futures.append(future)
        
        await asyncio.gather(*futures)
        logger.info(f"배치 발행 완료: {len(events)}개 이벤트")
    
    async def close(self):
        """리소스 정리"""
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        logger.info("Kafka 연결 종료")


kafka_manager = KafkaManager()


@asynccontextmanager
async def kafka_context():
    """Kafka 라이프사이클 관리"""
    await kafka_manager.init_producer()
    try:
        yield kafka_manager
    finally:
        await kafka_manager.close()
