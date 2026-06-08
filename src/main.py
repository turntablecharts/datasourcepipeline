from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.database import engine, Base
from src.auth.router import router as auth_router
from src.templates.router import router as templates_router
from src.weekly_data_cleaning.router import router as cleaning_router
from src.admin.router import router as admin_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

Base.metadata.create_all(bind=engine)

app = FastAPI(title="TTC Data Service")
app.mount("/static", StaticFiles(directory="src/static_ui"), name="static")


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(templates_router, prefix="/templates", tags=["templates"])
app.include_router(cleaning_router, prefix="/clean", tags=["cleaning"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

@app.get("/")
def root():
    return {"status": "ok", "service": "Data Cleaning Service"}