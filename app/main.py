from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import upload_routes, student_hierarchy_routes, analysis_routes
from DBController import db_router
import logging
from config import settings

def _configure_logging():
    level = getattr(logging, (settings.log_level or "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        )
    else:
        root.setLevel(level)
    logging.getLogger(__name__).info("Logging configured with level %s", logging.getLevelName(level))


_configure_logging()

app = FastAPI(title="Training Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload_routes.router, prefix="/api/v1")
app.include_router(student_hierarchy_routes.router, prefix="/api/v1")
app.include_router(analysis_routes.router, prefix="/api/v1")
app.include_router(db_router.router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True)
