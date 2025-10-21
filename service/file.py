import pathlib,subprocess
from fastapi import UploadFile
from defualt_render_list import *
from repository.minio import *

class FileService:
    def __init__(self,minioRepository: MinIORepository,file:UploadFile,rootProjectPath:str,renderedPath:str):
        self.minioRepo = minioRepository
        self.file = file
        self.rootProjectPath = rootProjectPath
        self.fileName = file.filename
        self.renderedPath = renderedPath
    
    def run(self,cmd, cwd=None):
        """Run subprocess command and raise error on failure"""
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=None)
        try:
            if proc.returncode != 0:
                raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        except NameError:
            print(NameError)
        return proc.stdout

    async def transcode_renditions(self, height:str , width:str, bitrate:str ,workdir: pathlib.Path,fileName:str):
        """Use ffmpeg to generate renditions (fMP4-ready)"""
        out_file = workdir + fileName + " " + f"{height}p.mp4"
        audio_bitrate_kbps = 128
        cmd = [
            "ffmpeg" , "-y", "-i", str(self.rootProjectPath),
            "-c:v", "libx264", "-profile:v", "main", "-preset", "veryfast",
            "-b:v", f"{bitrate}k",
            "-vf", f"scale=:w={width}:h={height}:force_original_aspect_ratio=decrease",
            "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
            "-movflags", "+faststart",
            str(out_file)
        ]
        self.run(cmd=cmd)
        return fileName+" "+f"{height}p.mp4"
    
    async def uploadFilesToMinio(self,renderedFiles:list):
        await self.minioRepo.uploadFiles(renderedFiles,self.renderedPath)
        # client = Minio(endpoint=cfg.minioHost+":"+cfg.minioPort,access_key=cfg.minioUsername,secret_key=cfg.minioPassword,secure=False)
        # minioRepository = MinIORepository(client=client,bucket=cfg.minioBucketName,directory=cfg.minioDirectory)
        # await minioRepository.uploadFiles(renderedFiles,self)

    async def rendetionFiles(self,renderedPath:str):
        fileNameWithOutSuffix = self.file.filename.removesuffix(".mp4")
        cmd = ["ffprobe", "-v" ,"error", "-select_streams" ,"v:0" ,"-show_entries", "stream=width,height" ,"-of" ,"csv=s=x:p=0", self.rootProjectPath]
        videoResolution = self.run(cmd=cmd)
        outputfiles = []
        for rosoulation in defualtRenderList:
            if rosoulation.get("width") <= int(videoResolution.split("x")[0]):
                outfile = await self.transcode_renditions(height=rosoulation.get("height"),width=rosoulation.get("width"),bitrate=rosoulation.get("video_bitrate_kbps"),workdir=renderedPath,fileName=fileNameWithOutSuffix)
                outputfiles.append(outfile)
    
        return outputfiles