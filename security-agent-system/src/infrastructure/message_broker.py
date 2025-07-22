"""Message broker implementations for RabbitMQ and Kafka."""
import json
import asyncio
from typing import Dict, Any, Callable, Awaitable, Optional
import structlog
import pika
import aio_pika
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from ..core.interfaces import IMessageBroker
from ..core.config import settings

logger = structlog.get_logger()


class RabbitMQBroker(IMessageBroker):
    """RabbitMQ message broker implementation."""
    
    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queues: Dict[str, aio_pika.Queue] = {}
        
    async def connect(self) -> None:
        """Establish connection to RabbitMQ."""
        try:
            self.connection = await aio_pika.connect_robust(
                f"amqp://{settings.broker_username}:{settings.broker_password}@"
                f"{settings.broker_host}:{settings.broker_port}/"
            )
            self.channel = await self.connection.channel()
            
            # Set prefetch count for load balancing
            await self.channel.set_qos(prefetch_count=10)
            
            # Declare queues
            for queue_name in [
                settings.hunting_queue,
                settings.execution_queue,
                settings.dead_letter_queue
            ]:
                queue = await self.channel.declare_queue(
                    queue_name,
                    durable=True,
                    arguments={
                        'x-message-ttl': 3600000,  # 1 hour TTL
                        'x-max-length': 10000,  # Max 10k messages
                    }
                )
                self.queues[queue_name] = queue
                
            logger.info("Connected to RabbitMQ", 
                       host=settings.broker_host,
                       port=settings.broker_port)
                       
        except Exception as e:
            logger.error("Failed to connect to RabbitMQ", error=str(e))
            raise
            
    async def disconnect(self) -> None:
        """Close connection to RabbitMQ."""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("Disconnected from RabbitMQ")
            
    async def publish(self, queue: str, message: Dict[str, Any]) -> None:
        """Publish a message to a queue."""
        if not self.channel:
            raise RuntimeError("Not connected to RabbitMQ")
            
        try:
            message_body = json.dumps(message).encode()
            await self.channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    content_type="application/json"
                ),
                routing_key=queue
            )
            
            logger.debug("Published message to queue",
                        queue=queue,
                        message_id=message.get('task_id', 'unknown'))
                        
        except Exception as e:
            logger.error("Failed to publish message",
                        queue=queue,
                        error=str(e))
            raise
            
    async def subscribe(
        self,
        queue: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Subscribe to a queue with a message handler."""
        if queue not in self.queues:
            raise ValueError(f"Queue {queue} not declared")
            
        async def process_message(message: aio_pika.IncomingMessage):
            """Process incoming message."""
            async with message.process():
                try:
                    body = json.loads(message.body.decode())
                    await handler(body)
                    
                except Exception as e:
                    logger.error("Failed to process message",
                               queue=queue,
                               error=str(e))
                    # Message will be requeued due to exception
                    raise
                    
        await self.queues[queue].consume(process_message)
        logger.info("Subscribed to queue", queue=queue)
        
    async def acknowledge(self, message_id: str) -> None:
        """Acknowledge successful message processing."""
        # Handled automatically by aio_pika context manager
        pass
        
    async def reject(self, message_id: str, requeue: bool = False) -> None:
        """Reject a message, optionally requeuing it."""
        # Handled automatically by aio_pika when exception is raised
        pass


class KafkaBroker(IMessageBroker):
    """Apache Kafka message broker implementation."""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.consumer_tasks: Dict[str, asyncio.Task] = {}
        
    async def connect(self) -> None:
        """Establish connection to Kafka."""
        try:
            # Create producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=f"{settings.broker_host}:{settings.broker_port}",
                value_serializer=lambda v: json.dumps(v).encode(),
                compression_type="gzip",
                acks="all",
                retries=3
            )
            await self.producer.start()
            
            logger.info("Connected to Kafka",
                       host=settings.broker_host,
                       port=settings.broker_port)
                       
        except Exception as e:
            logger.error("Failed to connect to Kafka", error=str(e))
            raise
            
    async def disconnect(self) -> None:
        """Close connection to Kafka."""
        # Stop all consumers
        for task in self.consumer_tasks.values():
            task.cancel()
            
        for consumer in self.consumers.values():
            await consumer.stop()
            
        # Stop producer
        if self.producer:
            await self.producer.stop()
            
        logger.info("Disconnected from Kafka")
        
    async def publish(self, queue: str, message: Dict[str, Any]) -> None:
        """Publish a message to a topic."""
        if not self.producer:
            raise RuntimeError("Not connected to Kafka")
            
        try:
            await self.producer.send_and_wait(queue, message)
            
            logger.debug("Published message to topic",
                        topic=queue,
                        message_id=message.get('task_id', 'unknown'))
                        
        except Exception as e:
            logger.error("Failed to publish message",
                        topic=queue,
                        error=str(e))
            raise
            
    async def subscribe(
        self,
        queue: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Subscribe to a topic with a message handler."""
        try:
            # Create consumer
            consumer = AIOKafkaConsumer(
                queue,
                bootstrap_servers=f"{settings.broker_host}:{settings.broker_port}",
                group_id=f"{queue}_consumer_group",
                value_deserializer=lambda v: json.loads(v.decode()),
                auto_offset_reset="earliest",
                enable_auto_commit=False
            )
            await consumer.start()
            self.consumers[queue] = consumer
            
            # Create consumer task
            async def consume_messages():
                """Consume messages from Kafka."""
                try:
                    async for msg in consumer:
                        try:
                            await handler(msg.value)
                            await consumer.commit()
                        except Exception as e:
                            logger.error("Failed to process message",
                                       topic=queue,
                                       error=str(e))
                                       
                except asyncio.CancelledError:
                    logger.info("Consumer task cancelled", topic=queue)
                    raise
                    
            task = asyncio.create_task(consume_messages())
            self.consumer_tasks[queue] = task
            
            logger.info("Subscribed to topic", topic=queue)
            
        except Exception as e:
            logger.error("Failed to subscribe to topic",
                        topic=queue,
                        error=str(e))
            raise
            
    async def acknowledge(self, message_id: str) -> None:
        """Acknowledge successful message processing."""
        # Handled by commit in Kafka
        pass
        
    async def reject(self, message_id: str, requeue: bool = False) -> None:
        """Reject a message."""
        # In Kafka, we would typically send to a DLQ
        if requeue:
            logger.warning("Kafka does not support message requeue directly")
