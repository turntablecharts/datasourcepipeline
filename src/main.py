from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from src.database import engine, Base
from src.auth.bootstrap import bootstrap_admin_user
from src.auth.router import router as auth_router
from src.templates.router import router as templates_router
from src.weekly_data_cleaning.router import router as cleaning_router
from src.admin.router import router as admin_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

Base.metadata.create_all(bind=engine)
bootstrap_admin_user()

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
    expose_headers=["Content-Disposition", "X-Replaced-Previous-Upload"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(templates_router, prefix="/templates", tags=["templates"])
app.include_router(cleaning_router, prefix="/clean", tags=["cleaning"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])

@app.get("/")
def root():
    return {"status": "ok", "service": "Data Service"}


@app.get("/debug/db")
def debug_db():
    try:
        with engine.connect() as connection:
            database_name = connection.execute(text("select current_database()")).scalar()
            database_user = connection.execute(text("select current_user")).scalar()
            table_rows = connection.execute(
                text(
                    """
                    select table_name
                    from information_schema.tables
                    where table_schema = 'public'
                    order by table_name
                    """
                )
            ).fetchall()
            user_count = None
            if any(row[0] == "users" for row in table_rows):
                user_count = connection.execute(text("select count(*) from users")).scalar()

        return {
            "status": "ok",
            "database": database_name,
            "user": database_user,
            "tables": [row[0] for row in table_rows],
            "users_count": user_count,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
