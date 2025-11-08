import asyncio
from config.config import Config
from service.file import FileService
from repository.minio import MinIORepository
from repository.mongo import MongoRepository
from fastapi import APIRouter, UploadFile, status, responses

router = APIRouter()

async def saveFile(fileName: str,filePath: str,key: str):
    cfg = Config()
    mongoRepo = MongoRepository()
    minioRepo = MinIORepository(bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    service = FileService(mongoRepository=mongoRepo,minioRepository=minioRepo,fileName=fileName,uploadedFilePath=filePath,renderedPath=cfg.renderedPath,outputPath=cfg.outputPath,key=key)

    renderedFiles = await service.rendetionFiles()
    await service.uploadFilesToMinio(renderedFiles)

@router.post("/uploadfile/")
async def create_upload_file(file: UploadFile,key: str):
    cfg = Config()
    file_path = cfg.outputPath + file.filename.replace(" ","")
    with open(file_path, "wb") as fi:
        fi.write(await file.read())
    asyncio.create_task(saveFile(fileName=file.filename.replace(" ",""),filePath=file_path,key=key))
    return responses.JSONResponse(content={"status":"ok"},status_code=status.HTTP_202_ACCEPTED)



