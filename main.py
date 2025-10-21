
from minio import Minio
from fastapi import FastAPI,UploadFile
from minio import Minio
from defualt_render_list import *
import io
from service.file import *
from repository.minio import *
from config.config import *
app = FastAPI()

@app.post("/uploadfile/")
async def create_upload_file(file :UploadFile):
    cfg = Config()
    with open(cfg.outputPath+file.filename,"wb") as fi:
        fi.write(file.file.read())
    
    minioConnection = Minio(endpoint=cfg.minioHost+":"+cfg.minioPort,access_key=cfg.minioUsername,secret_key=cfg.minioPassword,secure=False)
    minioRepo = MinIORepository(minioConnection,bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    service = FileService(minioRepository=minioRepo,file=file,rootProjectPath=cfg.outputPath+file.filename,renderedPath=cfg.renderdPath)

    renderedFiles = await service.rendetionFiles(renderedPath=cfg.renderdPath)
    await service.uploadFilesToMinio(renderedFiles)
    
    
    return {"uploaded": True, "file": file.filename, "size": "size"}