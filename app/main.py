import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .jobs.scheduler import start_scheduler, stop_scheduler
from .routers import auth, chat, dashboard, insights, planner, projects, settings as settings_router

settings = get_settings()
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
)
logger = logging.getLogger("odoopiai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    logger.info(
        "OdooPIAI up — model=%s fast_model=%s timezone=%s",
        settings.CLAUDE_MODEL,
        settings.CLAUDE_FAST_MODEL,
        settings.TIMEZONE,
    )
    yield
    stop_scheduler()


app = FastAPI(title="OdooPIAI", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(projects.router)
app.include_router(planner.router)
app.include_router(chat.router)
app.include_router(insights.router)
app.include_router(settings_router.router)


@app.get("/healthz")
def healthz():
    return {"ok": True, "version": "0.1.0"}
