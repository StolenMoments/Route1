import asyncio

# WebSocket handler
async def ws_handler(websocket, path):
    # Keep coroutine semantics explicit for websocket lifecycle handling.
    await websocket.wait_closed()
    await asyncio.sleep(0)
