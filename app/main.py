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

from fastapi.responses import HTMLResponse, Response

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <rect width="64" height="64" rx="16" fill="#0f172a"/>
  <rect x="3" y="3" width="58" height="58" rx="13" stroke="#3b82f6" stroke-opacity="0.35" stroke-width="2"/>
  <path d="M14 44V34M26 44V26M38 44V30M50 44V18" stroke="#38bdf8" stroke-width="4.5" stroke-linecap="round"/>
  <path d="M14 31L26 22L38 25L50 14" stroke="#10b981" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="50" cy="14" r="4" fill="#10b981"/>
</svg>"""

@app.get("/favicon.svg", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
async def serve_favicon():
    return Response(content=FAVICON_SVG, media_type="image/svg+xml")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

RUNTIME_PLATFORM_SETTINGS = {
    "autoOracleIntervalSec": 30,
    "priceTickerIntervalSec": 60,
    "showHeaderTickers": True,
    "defaultAccuracyPeriod": "1y",
    "defaultBaseRate": 50,
    "bayesianSensitivity": "standard",
    "infiniteScrollBatchSize": 6,
    "monochromeIcons": True,
    "showBottomPromptCapsule": True,
    "operatorName": "Локальный аналитик",
    "operatorRole": "Quant & Forecast Operator",
}

@app.get("/api/settings")
def get_platform_settings():
    return RUNTIME_PLATFORM_SETTINGS

@app.post("/api/settings")
async def update_platform_settings(request: Request):
    data = await request.json()
    if isinstance(data, dict):
        for k, v in data.items():
            if k in RUNTIME_PLATFORM_SETTINGS:
                RUNTIME_PLATFORM_SETTINGS[k] = v
    return {"status": "ok", "settings": RUNTIME_PLATFORM_SETTINGS}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
