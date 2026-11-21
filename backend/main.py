from dotenv import load_dotenv
load_dotenv()

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import engine, SessionLocal
from . import models
from .routers import answers, jobs, resume, settings as settings_router

models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from .services.scheduler import start_scheduler, stop_scheduler

    db = SessionLocal()
    try:
        s = db.query(models.Settings).filter(models.Settings.id == 1).first()
        start_scheduler(s.schedule_hour if s else 8, s.schedule_minute if s else 0,
                        bool(s and s.schedule_enabled))
    finally:
        db.close()
    yield
    stop_scheduler()


app = FastAPI(title="the_hunter", description="Job search, ranking and resume tailoring", lifespan=lifespan)

app.include_router(jobs.router, prefix="/api")
app.include_router(resume.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(answers.router, prefix="/api")

frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


@app.get("/")
def serve_frontend():
    return FileResponse(str(frontend_path / "index.html"))
