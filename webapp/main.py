from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bot.config import settings
from webapp.api import alerts, leverage, settings as settings_api, stats, trades, upload

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("meduz_webapp")

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bot = Bot(token=settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    logger.info("MEDUZ Mini App backend starting up")
    yield
    await app.state.bot.session.close()
    logger.info("MEDUZ Mini App backend shut down")


app = FastAPI(title="MEDUZ Trading Journal — Mini App API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(trades.router)
app.include_router(stats.router)
app.include_router(leverage.router)
app.include_router(alerts.router)
app.include_router(settings_api.router)
app.include_router(upload.router)


@app.get("/health")
async def health():
    return {"ok": True}


app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))
