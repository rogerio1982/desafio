from fastapi import FastAPI

from app.api.router import router

app = FastAPI(title="3D Digital Showroom AI", version="1.0.0")
app.include_router(router)
