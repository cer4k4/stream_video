from fastapi import FastAPI
from router import router
from fastapi.staticfiles import StaticFiles
app = FastAPI()
app.mount("/outputs", StaticFiles(directory="/home/aka/Templates/project/rendered"), name="outputs")
app.include_router(router)
