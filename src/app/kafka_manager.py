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
    """Kafka Producer/Consumer Management"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.partitioner_map = {}  # Partition cache
    
    async def init_producer(self):
        """Initialize Kafka Producer"""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=kafka_settings.bootstrap_servers,
            compression_type='snappy',
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
        )
        await self.producer.start()
        logger.info("Kafka Producer started")
    
    async def init_consumer(self, topic: str, callback: Callable):
        """Initialize Kafka Consumer"""
        self.consumer = AIOKafkaConsumer(
            topic,
            bootstrap_servers=kafka_settings.bootstrap_servers,
            group_id=kafka_settings.consumer_group,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        await self.consumer.start()
        logger.info(f"Kafka Consumer started: {topic}")
        
        # Message processing
        try:
            async for message in self.consumer:
                await callback(message.value)
        except Exception as e:
            logger.error(f"Consumer error: {e}")
        finally:
            await self.consumer.stop()
    
    async def send_event(self, topic: str, event: dict, partition_key: Optional[str] = None):
        """Publish event"""
        if not self.producer:
            raise RuntimeError("Producer not initialized")
        
        try:
            # Partition key: based on user_id or device_id (sharding)
            key = partition_key.encode('utf-8') if partition_key else None
            
            await self.producer.send_and_wait(
                topic,
                value=event,
                key=key,
                timestamp_ms=int(datetime.utcnow().timestamp() * 1000)
            )
            logger.debug(f"Event published [{topic}]: {event}")
        except KafkaError as e:
            logger.error(f"Publish failed: {e}")
            raise
    
    async def batch_send(self, topic: str, events: list[dict], partition_key: Optional[str] = None):
        """Batch publish (performance optimization)"""
        if not self.producer:
            raise RuntimeError("Producer not initialized")
        
        futures = []
        for event in events:
            key = partition_key.encode('utf-8') if partition_key else None
            future = self.producer.send(topic, value=event, key=key)
            futures.append(future)
        
        await asyncio.gather(*futures)
        logger.info(f"Batch publish complete: {len(events)} events")
    
    async def close(self):
        """Cleanup resources"""
        if self.producer:
            await self.producer.stop()
        if self.consumer:
            await self.consumer.stop()
        logger.info("Kafka connection closed")


kafka_manager = KafkaManager()


@asynccontextmanager
async def kafka_context():
    """Manage Kafka lifecycle"""
    await kafka_manager.init_producer()
    try:
        yield kafka_manager
    finally:
        await kafka_manager.close()
