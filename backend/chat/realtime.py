import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket
from redis.asyncio import Redis

from chat.setting import setting

logger = logging.getLogger("uvicorn.error")


@dataclass
class UnreadConnection:
    websocket: WebSocket
    group_id: int
    message_event: asyncio.Event = field(default_factory=asyncio.Event)


class RedisPubSubManager:
    def __init__(self, redis_url: str, channel: str) -> None:
        self.redis_url = redis_url
        self.channel = channel
        self.redis: Redis | None = None
        self.listener_task: asyncio.Task | None = None
        self.connections: dict[int, UnreadConnection] = {}
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        try:
            self.redis = Redis.from_url(self.redis_url, decode_responses=True)
            await self.redis.ping()
            self.listener_task = asyncio.create_task(self._listen_for_events())
            logger.info("Redis pub/sub connected on %s", self.channel)
        except Exception:
            logger.exception(
                "Redis pub/sub is unavailable, falling back to local-only delivery"
            )
            self.redis = None
            self.listener_task = None

    async def stop(self) -> None:
        if self.listener_task:
            self.listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.listener_task
            self.listener_task = None
        if self.redis:
            await self.redis.aclose()
            self.redis = None
        self.connections.clear()
        self._started = False

    def register_connection(
        self, user_id: int, group_id: int, websocket: WebSocket
    ) -> UnreadConnection:
        connection = UnreadConnection(websocket=websocket, group_id=group_id)
        self.connections[user_id] = connection
        return connection

    def unregister_connection(
        self, user_id: int, websocket: WebSocket | None = None
    ) -> None:
        connection = self.connections.get(user_id)
        if connection and (websocket is None or connection.websocket is websocket):
            self.connections.pop(user_id, None)

    def get_connection(self, user_id: int) -> UnreadConnection | None:
        return self.connections.get(user_id)

    async def publish_message(self, group_id: int) -> None:
        await self._publish({"kind": "message", "group_id": group_id})

    async def publish_change(self, group_id: int, change_data: dict[str, Any]) -> None:
        await self._publish(
            {"kind": "change", "group_id": group_id, "change": change_data}
        )

    async def _publish(self, event: dict[str, Any]) -> None:
        if not self.redis:
            await self._handle_event(event)
            return
        try:
            await self.redis.publish(self.channel, json.dumps(event))
        except Exception:
            logger.exception("Failed to publish Redis event, using local fallback")
            await self._handle_event(event)

    async def _listen_for_events(self) -> None:
        if not self.redis:
            return
        while True:
            pubsub = self.redis.pubsub()
            try:
                await pubsub.subscribe(self.channel)
                while True:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if not message:
                        await asyncio.sleep(0.1)
                        continue
                    await self._handle_event(json.loads(message["data"]))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Redis listener failed, reconnecting")
                await asyncio.sleep(1)
            finally:
                with contextlib.suppress(Exception):
                    await pubsub.unsubscribe(self.channel)
                with contextlib.suppress(Exception):
                    await pubsub.aclose()

    async def _handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("kind")
        group_id = int(event["group_id"])
        if kind == "message":
            self._wake_group(group_id)
            return
        if kind == "change":
            await self._send_change(group_id, event["change"])

    def _wake_group(self, group_id: int) -> None:
        for connection in self.connections.values():
            if connection.group_id == group_id:
                connection.message_event.set()

    async def _send_change(self, group_id: int, change_data: dict[str, Any]) -> None:
        payload = json.dumps(change_data)
        disconnected_users: list[int] = []
        for user_id, connection in list(self.connections.items()):
            if connection.group_id != group_id:
                continue
            try:
                await connection.websocket.send_text(payload)
            except Exception:
                disconnected_users.append(user_id)
        for user_id in disconnected_users:
            self.unregister_connection(user_id)


realtime = RedisPubSubManager(
    redis_url=setting.REDIS_URL,
    channel=setting.REDIS_CHANNEL,
)
