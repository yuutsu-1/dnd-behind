import asyncio
import json
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status

from app.core.security import decode_token
from app.core.redis import get_redis
from app.db.models.campaign import CampaignMember
from app.db.session import async_session
from sqlalchemy import select

router = APIRouter(tags=["websocket"])


async def _verify_ws_token(token: str) -> uuid.UUID | None:
    """Returns user_id if token is valid, else None."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None


async def _is_campaign_member(user_id: uuid.UUID, campaign_id: uuid.UUID) -> bool:
    async with async_session() as db:
        result = await db.execute(
            select(CampaignMember).where(
                CampaignMember.campaign_id == campaign_id,
                CampaignMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None


@router.websocket("/ws/campaign/{campaign_id}")
async def campaign_ws(
    websocket: WebSocket,
    campaign_id: uuid.UUID,
    token: str = Query(...),
):
    user_id = await _verify_ws_token(token)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not await _is_campaign_member(user_id, campaign_id):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()

    redis = get_redis()
    pubsub = redis.pubsub()
    channel = f"campaign:{campaign_id}"
    await pubsub.subscribe(channel)

    async def redis_to_ws():
        """Forward messages from Redis pub/sub to this WebSocket client."""
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    await websocket.send_text(message["data"])
        except Exception:
            pass

    relay_task = asyncio.create_task(redis_to_ws())

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "invalid JSON"}))
                continue

            # Stamp the actor and re-publish so all clients (including sender) see it
            event["actor_id"] = str(user_id)
            await redis.publish(channel, json.dumps(event))

    except WebSocketDisconnect:
        pass
    finally:
        relay_task.cancel()
        await pubsub.unsubscribe(channel)
