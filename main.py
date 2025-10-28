from fastapi import FastAPI
from router import router
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

#app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/outputs", StaticFiles(directory="/home/aka/Templates/project/outputs"), name="outputs")
app.include_router(router)
