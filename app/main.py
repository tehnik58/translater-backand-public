from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import router
from DBController.db_router import db_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # В продакшене лучше заменить на список конкретных доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api/v1", tags=["Records"])
app.include_router(db_router, prefix="/api/v1", tags=["DataController"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)