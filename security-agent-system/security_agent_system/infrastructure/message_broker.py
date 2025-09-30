"""RabbitMQ 和 Kafka 的訊息代理實作。"""
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
    """RabbitMQ 訊息代理實作。"""
    
    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queues: Dict[str, aio_pika.Queue] = {}
        
    async def connect(self) -> None:
        """建立與 RabbitMQ 的連線。"""
        try:
            self.connection = await aio_pika.connect_robust(
                f"amqp://{settings.broker_username}:{settings.broker_password}@"
                f"{settings.broker_host}:{settings.broker_port}/"
            )
            self.channel = await self.connection.channel()
            
            # 設定預取計數以進行負載平衡
            await self.channel.set_qos(prefetch_count=10)
            
            # 宣告佇列
            for queue_name in [
                settings.hunting_queue,
                settings.execution_queue,
                settings.dead_letter_queue
            ]:
                queue = await self.channel.declare_queue(
                    queue_name,
                    durable=True,
                    arguments={
                        'x-message-ttl': 3600000,  # 1 小時 TTL
                        'x-max-length': 10000,  # 最多 1 萬則訊息
                    }
                )
                self.queues[queue_name] = queue
                
            logger.info("已連接到 RabbitMQ",
                       host=settings.broker_host,
                       port=settings.broker_port)
                       
        except Exception as e:
            logger.error("連接到 RabbitMQ 失敗", error=str(e))
            raise
            
    async def disconnect(self) -> None:
        """關閉與 RabbitMQ 的連線。"""
        if self.connection and not self.connection.is_closed:
            await self.connection.close()
            logger.info("已從 RabbitMQ 斷開連線")
            
    async def publish(self, queue: str, message: Dict[str, Any]) -> None:
        """將訊息發布到佇列。"""
        if not self.channel:
            raise RuntimeError("未連接到 RabbitMQ")
            
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
            
            logger.debug("已將訊息發布到佇列",
                        queue=queue,
                        message_id=message.get('task_id', 'unknown'))
                        
        except Exception as e:
            logger.error("發布訊息失敗",
                        queue=queue,
                        error=str(e))
            raise
            
    async def subscribe(
        self,
        queue: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """使用訊息處理常式訂閱佇列。"""
        if queue not in self.queues:
            raise ValueError(f"佇列 {queue} 未宣告")
            
        async def process_message(message: aio_pika.IncomingMessage):
            """處理傳入的訊息。"""
            async with message.process():
                try:
                    body = json.loads(message.body.decode())
                    await handler(body)
                    
                except Exception as e:
                    logger.error("處理訊息失敗",
                               queue=queue,
                               error=str(e))
                    # 由於例外，訊息將被重新排入佇列
                    raise
                    
        await self.queues[queue].consume(process_message)
        logger.info("已訂閱佇列", queue=queue)
        
    async def acknowledge(self, message_id: str) -> None:
        """確認訊息成功處理。"""
        # 由 aio_pika 上下文管理器自動處理
        pass
        
    async def reject(self, message_id: str, requeue: bool = False) -> None:
        """拒絕訊息，可選擇性地重新排入佇列。"""
        # 當引發例外時由 aio_pika 自動處理
        pass


class KafkaBroker(IMessageBroker):
    """Apache Kafka 訊息代理實作。"""
    
    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None
        self.consumers: Dict[str, AIOKafkaConsumer] = {}
        self.consumer_tasks: Dict[str, asyncio.Task] = {}
        
    async def connect(self) -> None:
        """建立與 Kafka 的連線。"""
        try:
            # 建立生產者
            self.producer = AIOKafkaProducer(
                bootstrap_servers=f"{settings.broker_host}:{settings.broker_port}",
                value_serializer=lambda v: json.dumps(v).encode(),
                compression_type="gzip",
                acks="all",
                retries=3
            )
            await self.producer.start()
            
            logger.info("已連接到 Kafka",
                       host=settings.broker_host,
                       port=settings.broker_port)
                       
        except Exception as e:
            logger.error("連接到 Kafka 失敗", error=str(e))
            raise
            
    async def disconnect(self) -> None:
        """關閉與 Kafka 的連線。"""
        # 停止所有消費者
        for task in self.consumer_tasks.values():
            task.cancel()
            
        for consumer in self.consumers.values():
            await consumer.stop()
            
        # 停止生產者
        if self.producer:
            await self.producer.stop()
            
        logger.info("已從 Kafka 斷開連線")
        
    async def publish(self, queue: str, message: Dict[str, Any]) -> None:
        """將訊息發布到主題。"""
        if not self.producer:
            raise RuntimeError("未連接到 Kafka")
            
        try:
            await self.producer.send_and_wait(queue, message)
            
            logger.debug("已將訊息發布到主題",
                        topic=queue,
                        message_id=message.get('task_id', 'unknown'))
                        
        except Exception as e:
            logger.error("發布訊息失敗",
                        topic=queue,
                        error=str(e))
            raise
            
    async def subscribe(
        self,
        queue: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]]
    ) -> None:
        """使用訊息處理常式訂閱主題。"""
        try:
            # 建立消費者
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
            
            # 建立消費者任務
            async def consume_messages():
                """從 Kafka 消費訊息。"""
                try:
                    async for msg in consumer:
                        try:
                            await handler(msg.value)
                            await consumer.commit()
                        except Exception as e:
                            logger.error("處理訊息失敗",
                                       topic=queue,
                                       error=str(e))
                                       
                except asyncio.CancelledError:
                    logger.info("消費者任務已取消", topic=queue)
                    raise
                    
            task = asyncio.create_task(consume_messages())
            self.consumer_tasks[queue] = task
            
            logger.info("已訂閱主題", topic=queue)
            
        except Exception as e:
            logger.error("訂閱主題失敗",
                        topic=queue,
                        error=str(e))
            raise
            
    async def acknowledge(self, message_id: str) -> None:
        """確認訊息成功處理。"""
        # 由 Kafka 中的 commit 處理
        pass
        
    async def reject(self, message_id: str, requeue: bool = False) -> None:
        """拒絕訊息。"""
        # 在 Kafka 中，我們通常會傳送到死信佇列 (DLQ)
        if requeue:
            logger.warning("Kafka 不直接支援訊息重新排入佇列")