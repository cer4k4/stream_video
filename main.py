
import shutil, pathlib, uuid, json, subprocess
from minio import Minio
from minio.error import S3Error
from typing import Annotated
from fastapi import FastAPI, File, UploadFile
from minio import Minio
from defualt_render_list import *
import io
from service.file import *
from repository.minio import *
from config.config import *
app = FastAPI()


# async def run(cmd, cwd=None):
#     """Run subprocess command and raise error on failure"""
#     proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
#     if proc.returncode != 0:
#         raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
#     return proc.stdout

# async def transcode_renditions(input_file: pathlib.Path, height:str , width:str, bitrate:str ,workdir: pathlib.Path,fileName:str):
#     """Use ffmpeg to generate renditions (fMP4-ready)"""
#     out_file = workdir + fileName + " " + f"{height}p.mp4"
#     audio_bitrate_kbps = 128
#     cmd = [
#         "ffmpeg", "-y", "-i", str(input_file),
#         "-c:v", "libx264", "-profile:v", "main", "-preset", "veryfast",
#         "-b:v", f"{bitrate}k",
#         "-vf", f"scale=:w={width}:h={height}:force_original_aspect_ratio=decrease",
#         "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
#         "-movflags", "+faststart",
#         str(out_file)
#     ]
#     await run(cmd)
#     return fileName+" "+f"{height}p.mp4"

# def create_directory(client: Minio,bucket: str,prefix: str):
#     """Create an empty folder marker object"""
#     data = io.BytesIO(b"")  #zero-byte
#     client.put_object(bucket, prefix, data, 0)

# def directory_exists(client: Minio,bucket: str, prefix: str) -> bool:
#     """Check if a prefix (directory) exists in MinIO"""
#     objects = client.list_objects(bucket, prefix=prefix, recursive=True)
#     return any(True for _ in objects)

@app.post("/uploadfile/")
async def create_upload_file(file :UploadFile):
    cfg = Config()
    with open(cfg.outputPath+file.filename,"wb") as fi:
        fi.write(file.file.read())
    # here is service layer
    # fileNameWithOutSuffix = file.filename.removesuffix(".mp4")
    # outputfiles = []
    # cmd = ["ffprobe", "-v" ,"error", "-select_streams" ,"v:0" ,"-show_entries", "stream=width,height" ,"-of" ,"csv=s=x:p=0", rootProjectPath]
    # videoResolution = await run(cmd)
    # for rosoulation in defualtRenderList:
    #     if rosoulation.get("width") <= int(videoResolution.split("x")[0]):
    #         outfile = await transcode_renditions(input_file=rootProjectPath,height=rosoulation.get("height"),width=rosoulation.get("width"),bitrate=rosoulation.get("video_bitrate_kbps"),workdir=renderedPath,fileName=fileNameWithOutSuffix)
    #         outputfiles.append(outfile)
    service = FileService(file=file,rootProjectPath=cfg.outputPath+file.filename)
    renderedFiles = await service.rendetionFiles(renderedPath=cfg.renderdPath)
    # here is minio Repo
    #MINIO_ENDPOINT = "172.16.152.47:9000"
    # minioDirectory = "nodejs/"
    # bucket_name = "aka-bucket"
    # found = client.bucket_exists(bucket_name=bucket_name)
    # if not found:
    #     client.make_bucket(bucket_name=bucket_name)
    #     print("Created bucket", bucket_name)
    # else:
    #     print("Bucket", bucket_name, "already exists")
    # """Return True if any object starts with prefix (simulate directory existence)"""
    # for o in outputfiles:
    #     source_file = renderedPath + o
    #     if not directory_exists(client=client,bucket=bucket_name,prefix=minioDirectory):
    #         create_directory(client=client,bucket=bucket_name,prefix=minioDirectory)
    #     else:
    #         client.fput_object(bucket_name=bucket_name,object_name=minioDirectory+o,file_path=source_file)
    client = Minio(endpoint=cfg.minioHost+":"+cfg.minioPort,access_key=cfg.minioUsername,secret_key=cfg.minioPassword,secure=False)
    minioRepository = MinIORepository(client=client,bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
    await minioRepository.uploadFiles(renderedFiles,cfg.renderdPath)
    
    return {"uploaded": True, "file": file.filename, "size": "size"}