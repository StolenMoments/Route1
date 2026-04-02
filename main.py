from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles

from config import HOST, PORT
from ws_handler import WsHandler


ws_handler = WsHandler()


@asynccontextmanager
async def lifespan(_: FastAPI):
    for manager in ws_handler.pty_managers.values():
        manager.start(ws_handler.cwd)
    try:
        yield
    finally:
        for manager in ws_handler.pty_managers.values():
            manager.stop()


app = FastAPI(lifespan=lifespan)


@app.websocket("/ws")
async def websocket_entrypoint(websocket: WebSocket):
    await ws_handler.handle_connection(websocket)


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run("main:app", host=HOST, port=PORT)
