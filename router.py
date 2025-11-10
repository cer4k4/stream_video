import asyncio
import hashlib
import binascii
import secrets
from config.config import Config
from service.file import FileService
from repository.minio import MinIORepository
from repository.mongo import MongoRepository
from fastapi import APIRouter, UploadFile, status, responses

router = APIRouter()

# TODO : it's middleware
def string_to_encryption_key(input_string: str, salt: bytes = None) -> str:
    """
    هر رشته‌ای رو به کلید ۱۶ بایتی (۳۲ کاراکتر هگز) تبدیل می‌کنه
    """
    if salt is None:
        salt = secrets.token_bytes(16)  # هر بار salt جدید (امن‌تر)

    # PBKDF2 با 100,000 دور (امن و قابل تنظیم)
    key = hashlib.pbkdf2_hmac(
        'sha256',                   # هش امن
        input_string.encode('utf-8'),  # ورودی به بایت
        salt,                       # salt
        100000,                     # تعداد دور (هر چی بیشتر، امن‌تر ولی کندتر)
        dklen=16                    # ۱۶ بایت = ۱۲۸ بیت
    )
    
    # به هگز تبدیل کن
    return binascii.hexlify(key).decode('ascii')


async def saveFile(fileName: str,filePath: str,drm: dict):
    cfg = Config()
    mongoRepo = MongoRepository()
    minioRepo = MinIORepository(bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    service = FileService(mongoRepository=mongoRepo,minioRepository=minioRepo,fileName=fileName,uploadedFilePath=filePath,renderedPath=cfg.renderedPath,outputPath=cfg.outputPath,drm=drm)

    renderedFiles = await service.rendetionFiles()
    await service.uploadFilesToMinio(renderedFiles)

async def get_file(filename: str):
    cfg = Config()
    mongoRepo = MongoRepository()
    minioRepo = MinIORepository(bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    drm = dict()
    drm = {'key': string_to_encryption_key("key"),'key_id': secrets.token_hex(16)}
    service = FileService(mongoRepository=mongoRepo,minioRepository=minioRepo,fileName="",uploadedFilePath="",renderedPath=cfg.renderedPath,outputPath=cfg.outputPath,drm=drm)
    objectfile = await service.get_path_of_files(fileName=filename)
    if objectfile:
        return objectfile
    else:
        print("No file found:", filename)
        return None

@router.post("/uploadfile/")
async def create_upload_file(file: UploadFile,key: str):
    cfg = Config()
    file_path = cfg.outputPath + file.filename.replace(" ","")
    with open(file_path, "wb") as fi:
        fi.write(await file.read())
    drm = dict()
    drm = {'key': string_to_encryption_key(key),'key_id': secrets.token_hex(16)}
    asyncio.create_task(saveFile(fileName=file.filename.replace(" ",""),filePath=file_path,drm=drm))
    return responses.JSONResponse(content={"key_id":drm.get("key"),"key":drm.get("key_id")},status_code=status.HTTP_202_ACCEPTED)

@router.get("/getfile/:{filename}")
async def get_file_by_name(filename: str):
    result = await get_file(filename=filename)
    return responses.JSONResponse(content={"object":result},status_code=status.HTTP_200_OK)

