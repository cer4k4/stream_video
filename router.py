import jwt
import secrets
import asyncio
import hashlib
import binascii
from typing import Dict, Any
from config.config import Config
from service.file import FileService
from datetime import datetime, timedelta
from repository.minio import MinIORepository
from repository.mongo import MongoRepository
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, UploadFile, status, responses, Request, HTTPException,Form

router = APIRouter()

# ⚙️ Secret key (use a long random string in production!)
SECRET_KEY = "your_secret_key_here"
ALGORITHM = "HS256"

def create_jwt_token(data: Dict[str, Any], expires_delta: timedelta = timedelta(minutes=15)) -> str:
    """
    Create a JWT token with payload and expiration.
    """
    payload = data.copy()
    expire = datetime.utcnow() + expires_delta
    payload.update({"exp": expire})
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_jwt_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode JWT token. Raises jwt.ExpiredSignatureError or jwt.InvalidTokenError if invalid.
    """
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


def make_hash(input_string: str, salt: bytes = b"fixed_salt_1234") -> str:
    """
    تولید هش امن از رشته ورودی.
    خروجی: رشته‌ی هگز ۳۲ کاراکتری (۱۶ بایت)
    """
    key = hashlib.pbkdf2_hmac(
        'sha256',               # الگوریتم هش
        input_string.encode(),  # تبدیل رشته به بایت
        salt,                   # salt برای امنیت بیشتر
        100_000,                # تعداد تکرار
        dklen=16                # طول خروجی = ۱۶ بایت (۱۲۸ بیت)
    )
    return binascii.hexlify(key).decode('ascii')


async def saveFile(fileName: str,filePath: str,drm: dict):
    cfg = Config()
    mongoRepo = MongoRepository()
    minioRepo = MinIORepository(bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    service = FileService(mongoRepository=mongoRepo,minioRepository=minioRepo,fileName=fileName,uploadedFilePath=filePath,renderedPath=cfg.renderedPath,outputPath=cfg.outputPath)
    await mongoRepo.insert_status(fileName,"rendering",drm)
    renderedFiles = await service.rendetionFiles()
    await mongoRepo.update_status(fileName,"creating DASH format")
    await service.create_dash_format(renderedFiles,drm)
    await mongoRepo.update_status(fileName,"creating HLS format")
    await service.create_hls_format(renderedFiles)
    outputfiles = service.list_files_in_directory()
    await mongoRepo.update_status(fileName,"uploading to minio")
    await service.minioRepository.uploadFiles(outputfiles,cfg.outputPath)
    await service.removeLocalFiles(renderedFiles,cfg.renderedPath)
    await service.removeLocalFiles(outputfiles,cfg.outputPath)
    await mongoRepo.update_status(fileName,"done")

@router.post("/uploadfile/")
async def create_upload_file(file: UploadFile,password: str):
    cfg = Config()
    file_path = cfg.outputPath + file.filename.replace(" ","")
    with open(file_path, "wb") as fi:
        fi.write(await file.read())
    drm = dict()
    drm = {'key': make_hash(password),'key_id': secrets.token_hex(16)}
    asyncio.create_task(saveFile(fileName=file.filename.replace(" ",""),filePath=file_path,drm=drm))
    return responses.JSONResponse(content={"key_id":drm.get("key_id"),"key":drm.get("key")},status_code=status.HTTP_202_ACCEPTED)

@router.post("/checkPassword/")
async def check_password(filename: str=Form(...),password: str=Form(...)):
    mongoRepo = MongoRepository()
    doc = await mongoRepo.get_status(filename)
    if dict(doc).get('password') != make_hash(password):
        return responses.JSONResponse(content={"message": "you don't have permission to this video"}, status_code=403)
    #jwt = create_jwt_token({"key_id": dict(doc).get('key_uuid'),"key": dict(doc).get('password')})
    return responses.JSONResponse(content={"key_id": dict(doc).get('key_uuid'),"key": dict(doc).get('password')},status_code=200)

# @router.get("/stream/{filename:path}")
# async def stream_from_minio(filename: str, request: Request):
#     try:
#         # Get object info
#         stat = minio_client.stat_object(BUCKET_NAME, filename)
#         file_size = stat.size

#         # Determine MIME type
#         ext = os.path.splitext(filename)[1]
#         content_type = MIME_MAP.get(ext, "application/octet-stream")

#         # Handle Range (for MP4 or TS)
#         range_header = request.headers.get("range")
#         if range_header:
#             byte1, byte2 = 0, None
#             m = range_header.replace("bytes=", "").split("-")
#             if m[0]: byte1 = int(m[0])
#             if m[1]: byte2 = int(m[1])

#             length = (byte2 or file_size - 1) - byte1 + 1
#             range_str = f"bytes={byte1}-{byte1 + length - 1}"

#             response = minio_client.get_object(
#                 BUCKET_NAME, filename, request_headers={"Range": range_str}
#             )

#             headers = {
#                 "Content-Range": f"bytes {byte1}-{byte1 + length - 1}/{file_size}",
#                 "Accept-Ranges": "bytes",
#                 "Content-Length": str(length),
#                 "Content-Type": content_type,
#             }

#             return StreamingResponse(response, headers=headers, status_code=206)

#         # No range — return full object
#         response = minio_client.get_object(BUCKET_NAME, filename)
#         return StreamingResponse(response, media_type=content_type)

#     except Exception as e:
#         raise HTTPException(status_code=404, detail=str(e))
    
@router.get("/stream/{filename:path}")
async def stream_from_minio(filename: str, request: Request):
    cfg = Config()
    minioRepo = MinIORepository(bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    try:
        response, headers, status = minioRepo.get_file_stream(filename, request.headers.get("range"))
        return StreamingResponse(response, headers=headers, status_code=status)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal server error")
    