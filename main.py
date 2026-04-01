from fastapi import FastAPI
from routes import router

app = FastAPI()
app.include_router(router, prefix="/api/v1", tags=["Records"])


#if __name__ == "__main__":
#    import uvicorn
#    uvicorn.run(app, host="127.0.0.1", port=8080)