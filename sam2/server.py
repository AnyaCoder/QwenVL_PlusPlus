import os
from contextlib import asynccontextmanager
from threading import Thread

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.endpoints import setup_routes
from services.model_service import model_service
from worker.task_worker import TASK_QUEUE, TASK_STATUS, worker_loop


@asynccontextmanager
async def lifespan(app: FastAPI):

    model_service._load_models()
    Thread(target=worker_loop, daemon=True).start()
    logger.info("SAM2 models loaded and worker started.")
    yield

    model_service.cleanup()


app = FastAPI(
    lifespan=lifespan,
    title="SAM2 + Qwen-VL Video Analysis Service",
    description="视频分割和分析服务，集成SAM2和Qwen-VL模型",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


setup_routes(app)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
