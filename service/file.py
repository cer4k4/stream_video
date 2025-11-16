import re
import os
from enums import *
import pathlib,subprocess
from repository.minio import *
from repository.mongo import MongoRepository

    
class FileService:
    def __init__(self,mongoRepository: MongoRepository,minioRepository: MinIORepository,uploadedFilePath: str,renderedPath: str,fileName: str, outputPath: str):
        self.mongoRepository = mongoRepository
        self.minioRepository = minioRepository
        self.uploadedFilePath = uploadedFilePath
        self.renderedPath = renderedPath
        self.outPutPath = outputPath
        self.fileName = fileName

    async def extract_audio_to_aac(self):
        """
        Extract audio from the ORIGINAL uploaded file and convert to AAC
        """
        audio_out = f"{self.outPutPath}audio.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self.uploadedFilePath),
            "-vn",               # no video
            "-acodec", "aac",    # convert audio to AAC
            "-b:a", "128k",
            str(audio_out)
        ]
        self.run(cmd)
        return audio_out

    def getFileNameFormat(self):
        for format in formats:
            if self.fileName.endswith(format):
                return format
            
    def checkFileNameFormat(self):
        cmd = ["ffprobe" , "-v" , "error" ,"-show_entries" ,"format=format_name" , "-of" ,"default=noprint_wrappers=1:nokey=1" ,f"{self.outPutPath}{self.fileName}" ]
        output = self.run(cmd)
        names = output.split(",")
        if len(names) > 2:
            for n in names:
                if n in formats:
                    return True
    
        if output[:-1] in formats:
            return True
        
            
    def convert_to_mp4(self,input_file: str, output_file: str):
        format = self.getFileNameFormat()
        cmd = [
            "ffmpeg", "-y",
            "-i", input_file,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            f"{output_file}{self.fileName.removesuffix(format)}.mp4"
        ]
        subprocess.run(cmd, check=True)
        self.uploadedFilePath = f"{output_file}{self.fileName.removesuffix(format)}.mp4"
        #self.fileName = f"{self.fileName.removesuffix(format)}.mp4"
        return output_file

    def run(self,cmd, cwd=None):
        """Run subprocess command and raise error on failure"""
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=None)
        try:
            if proc.returncode != 0:
                raise RuntimeError(f"Command failed: {' '.join(cmd)}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        except NameError:
            print(NameError)
        return proc.stdout

    async def transcode_renditions(self, height: str, width: str, bitrate: str, workdir: pathlib.Path, fileName: str):

        """Use ffmpeg to generate fMP4 renditions ready for DASH/HLS"""
            
        out_file = workdir+f"{fileName}{height}p.mp4"  # بدون فاصله
        audio_bitrate_kbps = 128
        cmd = [
            "ffmpeg", "-y", "-i", str(self.uploadedFilePath),
            "-c:v", "libx264", "-profile:v", "main", "-preset", "veryfast",
            "-b:v", f"{bitrate}k",
            "-vf", f"scale=w={width}:h={height}:force_original_aspect_ratio=decrease",
            "-c:a", "aac", "-b:a", f"{audio_bitrate_kbps}k",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof",  
            str(out_file)
        ]
        self.run(cmd)
        return f"{fileName}{height}p.mp4"

    async def rendetionFiles(self):
        format = self.getFileNameFormat()
        fileNameWithOutSuffix = self.fileName.removesuffix(format)
        cmd = ["ffprobe", "-v" ,"error", "-select_streams" ,"v:0" ,"-show_entries", "stream=width,height" ,"-of" ,"csv=s=x:p=0", self.uploadedFilePath]
        videoResolution = self.run(cmd=cmd)
        outputfiles = []
        await self.mongoRepository.update_status(self.fileName,"rendering")
        for rosoulation in defualtRenderList:
            if rosoulation.get("width") <= int(videoResolution.split("x")[0]):
                outfile = await self.transcode_renditions(height=rosoulation.get("height"),width=rosoulation.get("width"),bitrate=rosoulation.get("video_bitrate_kbps"),workdir=self.renderedPath,fileName=fileNameWithOutSuffix)
                outputfiles.append(outfile)
        return outputfiles
    
    async def removeLocalFiles(self,renderedFiles: list,Path: str):
        if renderedFiles is None:
            self.run(["rm",Path])
            return
        for f in renderedFiles:
            cmd = ["rm",Path+f]
            self.run(cmd)

    async def create_hls_format(self, rendered_files: list):
        """
        Package videos into HLS variants and create a master playlist with all resolutions.
        """
        output_dir = pathlib.Path("/home/aka/Templates/project/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        master_playlist = self.outPutPath + "master.m3u8"

        variant_playlists = []
        for f in rendered_files:
            name, ext = os.path.splitext(f)
            match = re.match(r"^(.*?)(\d{3,4}p)$", name)
            if match:
                resolution = match.group(2)
                #print("Resolution:", f, resolution)

                # Example: segment_720p_%03d.ts and 720p.m3u8
                variant_playlist = output_dir / f"{name}.m3u8"
                segment_pattern = output_dir / f"{name}_%03d.ts"

                cmd = [
                    "ffmpeg", "-i", f'{self.renderedPath}{f}',
                    "-c:v", "libx264", "-preset", "veryfast",
                    "-c:a", "aac", "-f", "hls",
                    "-hls_time", "6",
                    "-hls_playlist_type", "vod",
                    "-hls_segment_filename", str(segment_pattern),
                    str(variant_playlist)
                ]
                self.run(cmd)

                # Add to master list
                variant_playlists.append((resolution, variant_playlist))
            else:
                print("No resolution found in filename.")

        # --- Generate master playlist ---
        with open(master_playlist, "w") as m3u8:
            m3u8.write("#EXTM3U\n")
            for res, playlist in variant_playlists:
                # You can adjust BANDWIDTH values per resolution
                bandwidth = {
                    "480p": 800000,
                    "720p": 2000000,
                    "1080p": 5000000,
                }.get(res, 1500000)
                m3u8.write(f"#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},RESOLUTION={res}\n")
                m3u8.write(f"{playlist.name}\n")

        #print(f"✅ Master playlist created at: {master_playlist}")
        return variant_playlists

    async def create_dash_format(self, rendered_files: list,drm: dict):
        #output_dir = pathlib.Path("/home/aka/Templates/project/outputs")
        audio_file = await self.extract_audio_to_aac()  # from ORIGINAL file
        manifest_mpd = self.outPutPath + "manifest.mpd"
        input_tracks = []
        for f in rendered_files:
            height = f.replace("p.mp4", "")
            input_tracks.append(f"in={self.renderedPath}{f},stream=video,output={self.outPutPath}video_{height}p.mp4")
        input_tracks.append(f"in={audio_file},stream=audio,output={self.outPutPath}audio.mp4")
        cmd = [
            "packager",
            *input_tracks,
            f"--mpd_output={manifest_mpd}",
            f"--hls_base_url={self.outPutPath}",
            "--generate_static_live_mpd",
            "--enable_raw_key_encryption",
            "--keys",
            f"label=:key_id={drm.get("key_id")}:key={drm.get("key")}",
            "--protection_scheme", "cenc"
        ]
        self.run(cmd)
        return str(manifest_mpd)

    def list_files_in_directory(self) -> list:
        try:
            # List all files in the directory (exclude subdirectories)
            files = [f for f in os.listdir(self.outPutPath) if os.path.isfile(os.path.join(self.outPutPath, f))]
            return files
        except FileNotFoundError:
            print(f"Error: The directory '{self.outPutPath}' was not found.")
            return []
        except PermissionError:
            print(f"Error: Permission denied for directory '{self.outPutPath}'.")
            return []
        
