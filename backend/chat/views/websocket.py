import asyncio
import contextlib
import json

from fastapi import Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from chat import app, logger, models
from chat.crud import (
    create_message_controller,
    create_unread_message_controller,
    get_group_by_id,
    group_membership_check,
)
from chat.database import get_db
from chat.models import Message, User
from chat.realtime import UnreadConnection, realtime
from chat.utils.jwt import get_current_user


@app.websocket("/send-message")
async def send_messages_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    """
    User send message api
    - token [str]
    - group_id [int]

    [in websocket]
    - text

    output:
     - None
    """
    token = websocket.query_params.get("token")
    group_id = websocket.query_params.get("group_id")
    if token and group_id:
        user = await get_current_user(user_db=db, token=token)
        group_id = int(group_id)
    else:
        return await websocket.close(reason="You're not allowed", code=4403)
    is_group_member = await group_membership_check(
        group_id=group_id,
        db=db,
        user=user,
    )
    if not is_group_member:
        logger.error(
            "User %s Connect to Send Messages But not allowed with group id : %s",
            user.username,
            group_id,
        )
        return await websocket.close(reason="You're not allowed", code=4403)
    if user:
        logger.info(
            "User %s Connect to Send Messages endpoint group id : %s",
            user.username,
            group_id,
        )
        await websocket.accept()
        while True:
            try:
                data = await websocket.receive_text()
            except WebSocketDisconnect as error_message:
                logger.info(
                    "User %s Disconnect from Send Messages endpoint group id : %s, %s",
                    user.username,
                    group_id,
                    error_message,
                )
                break
            if data is None:
                break
            message = await create_message_controller(
                db=db, user=user, group_id=group_id, text=data
            )
            # Broadcast the message to all users in the group
            asyncio.create_task(broadcast_message(group_id, message, db))


async def broadcast_message(group_id: int, message: Message, db) -> None:
    """
    Persist unread rows and notify all app instances for this group.
    - group_id [int]
    - message [Message]

    output:
    - None
    """
    group = await get_group_by_id(db=db, group_id=group_id)
    if group:
        for member in group.members:
            await create_unread_message_controller(
                db=db,
                message=message,
                user=member.user,
                group_id=group_id,
            )
        await realtime.publish_message(group_id)


@app.websocket("/get-unread-messages")
async def send_unread_messages_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    """
    Send unread messages
    - token [str]
    - group_id [int]

    [in websocket]
    - message

    output:
     - None
    """
    token = websocket.query_params.get("token")
    group_id = websocket.query_params.get("group_id")
    if token and group_id:
        user = await get_current_user(user_db=db, token=token)
        group_id = int(group_id)
    else:
        return await websocket.close(reason="You're not allowed", code=4403)
    is_group_member = await group_membership_check(
        group_id=group_id,
        db=db,
        user=user,
    )
    if not is_group_member:
        return await websocket.close(reason="You're not allowed", code=4403)
    if user:
        if realtime.get_connection(user.id):
            logger.error(
                "User %s Has More Than 1 Websocket With Group id : %s",
                user.username,
                group_id,
            )
            return await websocket.close(reason="You're not allowed", code=4403)
        await websocket.accept()
        realtime.register_connection(user.id, group_id, websocket)
        try:
            await send_unread_messages(websocket, user, group_id, db)
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            realtime.unregister_connection(user.id, websocket)
    else:
        return await websocket.close()


async def send_unread_messages(
    websocket: WebSocket,
    user: User,
    group_id: int,
    db: Session = Depends(get_db),
):
    """send unread messages to client"""
    while True:
        unread_messages_group = await flush_unread_messages(
            websocket=websocket,
            user=user,
            group_id=group_id,
            db=db,
        )
        if unread_messages_group:
            continue
        connection = realtime.get_connection(user.id)
        if not connection or connection.websocket is not websocket:
            break
        await wait_for_message_or_disconnect(connection)


async def flush_unread_messages(
    websocket: WebSocket,
    user: User,
    group_id: int,
    db: Session,
) -> list[models.UnreadMessage]:
    db.refresh(user)
    all_unread_messages = list(user.unread_messages or [])
    unread_messages_group = [
        unread_message
        for unread_message in all_unread_messages
        if unread_message.group_id == group_id
    ]
    if not unread_messages_group:
        return []
    await send_messages_concurrently(websocket, unread_messages_group)
    for unread_message in unread_messages_group:
        db.delete(unread_message)
    db.commit()
    return unread_messages_group


async def wait_for_message_or_disconnect(connection: UnreadConnection) -> None:
    message_task = asyncio.create_task(connection.message_event.wait())
    disconnect_task = asyncio.create_task(connection.websocket.receive())
    done, pending = await asyncio.wait(
        {message_task, disconnect_task},
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    if disconnect_task in done:
        message = disconnect_task.result()
        if message["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(message.get("code", 1000))
    if message_task in done and connection.message_event.is_set():
        connection.message_event.clear()


async def broadcast_changes(
    group_id: int,
    change_type: models.ChangeType,
    db: Session,
    message_id: int | None = None,
    new_text: str | None = None,
) -> None:
    """
    Broadcast changes to every app instance with listeners on that group.
    - group_id [int]
    - change_type [str]
    - message_id [int]
    - new_text [str]

    output:
    - None
    """
    changed_value = {
        "type": change_type.value,
        "id": message_id,
        "new_text": new_text,
    }
    await realtime.publish_change(group_id=group_id, change_data=changed_value)


async def send_messages_concurrently(
    websocket: WebSocket, messages: list[models.UnreadMessage]
):
    """Send Messages"""
    tasks = [
        websocket.send_text(
            json.dumps(
                {
                    "text": message.message.text,
                    "sender_name": message.message.sender_name,
                    "id": message.message.id,
                    "type": "Text",
                    "datetime": str(message.message.created_at),
                }
            )
        )
        for message in messages
    ]
    await asyncio.gather(*tasks)
