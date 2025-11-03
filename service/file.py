import pathlib,subprocess
from repository.minio import *
from fastapi import UploadFile
from defualt_render_list import *
from repository.mongo import MongoRepository


class FileService:
    def __init__(self,mongoRepository: MongoRepository,minioRepository: MinIORepository,rootProjectPath: str,renderedPath: str,fileName: str):
        self.mongoRepository = mongoRepository
        self.minioRepository = minioRepository
        self.rootProjectPath = rootProjectPath
        self.renderedPath = renderedPath
        self.fileName = fileName
    
    def run(self,cmd, cwd=None):
        """Run subprocess command and raise error on failure"""
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=None)
        try:
            if proc.returncode != 0:
                raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        except NameError:
            print(NameError)
        return proc.stdout

    # async def transcode_renditions(self, height:str , width:str, bitrate:str ,workdir: pathlib.Path,fileName:str):
    #     """Use ffmpeg to generate renditions (fMP4-ready)"""
    #     out_file = workdir + fileName + " " + f"{height}p.mp4"
    #     audio_bitrate_kbps = 128
    #     cmd = [
    #         "ffmpeg" , "-y", "-i", str(self.rootProjectPath),
    #         "-c:v", "libx264", "-profile:v", "main", "-preset", "veryfast",
    #         "-b:v", f"{bitrate}k",
    #         "-vf", f"scale=:w={width}:h={height}:force_original_aspect_ratio=decrease",
    #         "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
    #         "-movflags", "+faststart",
    #         str(out_file)
    #     ]
    #     self.run(cmd=cmd)
    #     return fileName+" "+f"{height}p.mp4"

    async def transcode_renditions(self, height: str, width: str, bitrate: str, workdir: pathlib.Path, fileName: str):
        """Use ffmpeg to generate fMP4 renditions ready for DASH/HLS"""
        out_file = workdir+f"{fileName}{height}p.mp4"  # بدون فاصله
        audio_bitrate_kbps = 128
        cmd = [
            "ffmpeg", "-y", "-i", str(self.rootProjectPath),
            "-c:v", "libx264", "-profile:v", "main", "-preset", "veryfast",
            "-b:v", f"{bitrate}k",
            "-vf", f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease",
            "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof",  # مهم برای shaka-packager
            str(out_file)
        ]
        self.run(cmd)
        return f"{fileName}{height}p.mp4"

    async def uploadFilesToMinio(self,renderedFiles: list):
        # await self.mongoRepository.update_status(self.fileName,"uploading in minio")
        # await self.minioRepository.uploadFiles(renderedFiles,self.renderedPath)
        # await self.package_to_cmaf(renderedFiles)
        # await self.removeLocalFiles(renderedFiles)
        # await self.mongoRepository.update_status(self.fileName,"done")
        await self.package_hls_to_ts()

    async def rendetionFiles(self,renderedPath:str):
        fileNameWithOutSuffix = self.fileName.removesuffix(".mp4")
        cmd = ["ffprobe", "-v" ,"error", "-select_streams" ,"v:0" ,"-show_entries", "stream=width,height" ,"-of" ,"csv=s=x:p=0", self.rootProjectPath]
        videoResolution = self.run(cmd=cmd)
        outputfiles = []
        await self.mongoRepository.update_status(self.fileName,"rendering")
        for rosoulation in defualtRenderList:
            if rosoulation.get("width") <= int(videoResolution.split("x")[0]):
                outfile = await self.transcode_renditions(height=rosoulation.get("height"),width=rosoulation.get("width"),bitrate=rosoulation.get("video_bitrate_kbps"),workdir=renderedPath,fileName=fileNameWithOutSuffix)
                outputfiles.append(outfile)
        return outputfiles
    
    async def removeLocalFiles(self,renderedFiles: list):
        # Remove first uploaded File that gave from enduser
        cmd = ["rm",self.rootProjectPath]
        self.run(cmd)
        # Remove Rendered Files
        for f in renderedFiles:
            cmd = ["rm",self.renderedPath+f]
            self.run(cmd)

    async def package_to_cmaf(self, rendered_files: list):
        """
        Package renditions to CMAF (DASH + HLS)
        """
        job_dir = pathlib.Path(self.renderedPath)
        manifest_mpd = job_dir / "manifest.mpd"
        manifest_m3u8 = job_dir / "master.m3u8"

        input_tracks = []
        for f in rendered_files:
            height = f.replace("p.mp4", "")
            input_tracks.append(
                f"in={job_dir}/{f},stream=video,output={job_dir}/video_{height}p.mp4"
            )

        input_tracks.append(
            f"in={self.rootProjectPath},stream=audio,output={job_dir}/audio.mp4"
        )
        cmd = [
            "packager",
            *input_tracks,
            f"--mpd_output={manifest_mpd}",
            f"--hls_master_playlist_output={manifest_m3u8}",
            "--hls_base_url=/outputs/",
            "--generate_static_live_mpd",
        ]

        print("Running:", " ".join(cmd))
        self.run(cmd)

        return str(manifest_mpd), str(manifest_m3u8)
    
    async def package_hls_to_ts(self):
        print("hiiiiii")
        """
        Package video into traditional HLS with .ts segments.
        """
        # job_dir = pathlib.Path(self.renderedPath)
        out_playlist = "/home/aka/Templates/project/outputs/master.m3u8"
        segment_pattern = "/home/aka/Templates/project/outputs/segment_%03d.ts"

        cmd = [
            "ffmpeg", "-i", str(self.rootProjectPath),
            "-c:v", "libx264", "-preset", "veryfast",
            "-c:a", "aac", "-f", "hls",
            "-hls_time", "6",
            "-hls_playlist_type", "vod",
            "-hls_segment_filename", str(segment_pattern),
            str(out_playlist)
        ]
        self.run(cmd)
        return str(out_playlist)
    

    
