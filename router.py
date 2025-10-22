from config.config import Config
from service.file import FileService
from fastapi import APIRouter, UploadFile
from repository.minio import MinIORepository
from repository.mongo import MongoRepository

router = APIRouter()

@router.post("/uploadfile/")
async def create_upload_file(file: UploadFile):
    fileStatus: str
    cfg = Config()
    file_path = cfg.outputPath + file.filename
    with open(file_path, "wb") as fi:
        fi.write(await file.read())

    mongoRepo = MongoRepository()
    minioRepo = MinIORepository(bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    service = FileService(mongoRepository=mongoRepo,minioRepository=minioRepo,file=file,rootProjectPath=file_path,renderedPath=cfg.renderedPath)

    renderedFiles = await service.rendetionFiles(renderedPath=cfg.renderedPath)
    try:
        await service.uploadFilesToMinio(renderedFiles)
        return {"file-status":"done"}
    except NameError:
        return {"file-status":"faild"}
