import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chat.database import Base, engine
from chat.realtime import realtime

__version__ = "1"
app = FastAPI(
    title="ChatProvider",
    description="A ChatProvider Based on WebSocket",
    version=__version__,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
logger = logging.getLogger("uvicorn.error")


@app.on_event("startup")
async def startup_realtime() -> None:
    Base.metadata.create_all(bind=engine)
    await realtime.start()


@app.on_event("shutdown")
async def shutdown_realtime() -> None:
    await realtime.stop()
