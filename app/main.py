import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database.session import init_db
from app.api import speakers, events, statements, demo, crypto_seed, sources, discovery, oracle
from app.oracles.auto_oracle import AutoOracleService

# Initialize database tables
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Launch auto oracle background monitor
    await AutoOracleService.start_background_worker()
    yield
    # Shutdown: Stop worker cleanly
    await AutoOracleService.stop_background_worker()

app = FastAPI(
    title=settings.APP_NAME,
    description="Платформа вероятностной оценки событий по заявлениям экспертов с учетом их исторической правдивости и Brier Score.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Template setup
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Include Routers
app.include_router(speakers.router)
app.include_router(events.router)
app.include_router(statements.router)
app.include_router(demo.router)
app.include_router(crypto_seed.router)
app.include_router(sources.router)
app.include_router(discovery.router)
app.include_router(oracle.router)

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
