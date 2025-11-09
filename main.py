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

app.mount("/outputs", StaticFiles(directory="/home/aka/Templates/project/outputs"), name="outputs")
app.mount("/rendered", StaticFiles(directory="/home/aka/Templates/project/rendered"), name="rendered")
app.include_router(router)
