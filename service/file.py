import re
import os
import pathlib,subprocess
from repository.minio import *
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
        await self.package_to_cmaf(renderedFiles)
        # await self.removeLocalFiles(renderedFiles)
        # await self.mongoRepository.update_status(self.fileName,"done")
        # await self.package_hls_to_ts(renderedFiles)

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

    async def package_hls_to_ts(self, rendered_files: list):
        """
        Package videos into HLS variants and create a master playlist with all resolutions.
        """
        output_dir = pathlib.Path("/home/aka/Templates/project/outputs")
        output_dir.mkdir(parents=True, exist_ok=True)
        master_playlist = output_dir / "master.m3u8"

        variant_playlists = []

        for f in rendered_files:
            name, ext = os.path.splitext(f)
            match = re.match(r"^(.*?)(\d{3,4}p)$", name)
            if match:
                resolution = match.group(2)
                print("Resolution:", f, resolution)

                # Example: segment_720p_%03d.ts and 720p.m3u8
                variant_playlist = output_dir / f"{resolution}.m3u8"
                segment_pattern = output_dir / f"segment_{resolution}_%03d.ts"

                cmd = [
                    "ffmpeg", "-i", f'/home/aka/Templates/project/rendered/{f}',
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

        print(f"✅ Master playlist created at: {master_playlist}")
        return str(master_playlist)

    async def package_to_cmaf(self, rendered_files: list):
        job_dir = "/home/aka/Templates/project/rendered"
        manifest_mpd = job_dir + "/manifest.mpd"
        manifest_m3u8 = job_dir + "/master.m3u8"

        input_tracks = []
        for f in rendered_files:
            height = f.replace("p.mp4", "")
            input_tracks.append(
                f"in={job_dir}/{f},stream=video,output={job_dir}/video_{height}p.mp4"
            )

        input_tracks.append(
            f"in={self.rootProjectPath},stream=audio,output={job_dir}/audio.mp4"
        )

        # cmd = [
        #     "packager",
        #     # Video renditions
        #     *[
        #         f"in={job_dir}/{f},stream=video,init_segment={job_dir}/{f.replace('.mp4', '_init.mp4')},"
        #         f"segment_template={job_dir}/{f.replace('.mp4', '_$Number$.m4s')}"
        #         for f in rendered_files
        #     ],
        #     # Audio track
        #     f"in={self.rootProjectPath},stream=audio,init_segment={job_dir}/audio_init.mp4,segment_template={job_dir}/audio_$Number$.m4s",
        #     # Outputs
        #     f"--mpd_output={manifest_mpd}",
        #     f"--hls_master_playlist_output={manifest_m3u8}",
        #     "--hls_base_url=/outputs/",
        #     "--generate_static_mpd",                     # ✅ for VOD
        #     "--enable_raw_key_encryption",
        #     "--keys",
        #     "label=:key_id=1234567890abcdef1234567890abcdef:key=abcdefabcdefabcdefabcdefabcdefab",
        #     "--protection_scheme", "cenc"
        # ]

        cmd = [
            "packager",
            *input_tracks,
            f"--mpd_output={manifest_mpd}",
            f"--hls_master_playlist_output={manifest_m3u8}",
            "--hls_base_url=/outputs/",
            "--generate_static_live_mpd",
            "--enable_raw_key_encryption",
            "--keys",
            "label=:key_id=1234567890abcdef1234567890abcdef:key=abcdefabcdefabcdefabcdefabcdefab",
            "--protection_scheme", "cenc"
        ]

        print("Running:", " ".join(cmd))
        self.run(cmd)
        return str(manifest_mpd), str(manifest_m3u8)
    
    # async def package_hls_to_ts(self,rendered_files: list):
    #     """
    #     Package video into traditional HLS with .ts segments.
    #     """
    #     #job_dir = pathlib.Path(self.renderedPath)
    #     for f in rendered_files:
    #         name, ext = os.path.splitext(f)
    #         match = re.match(r"^(.*?)(\d{3,4}p)$", name)
    #         if match:
    #             resolution = match.group(2)
    #             print("Resolution:",f, resolution)
    #             out_playlist = "/home/aka/Templates/project/outputs/master.m3u8"
    #             segment_pattern = f"/home/aka/Templates/project/outputs/segment_{resolution}_%03d.ts"
    #             cmd = [
    #                 "ffmpeg", "-i", f'/home/aka/Templates/project/rendered/{f}',
    #                 "-c:v", "libx264", "-preset", "veryfast",
    #                 "-c:a", "aac", "-f", "hls",
    #                 "-hls_time", "6",
    #                 "-hls_playlist_type", "vod",
    #                 "-hls_segment_filename", str(segment_pattern),
    #                 str(out_playlist)
    #             ]
    #             self.run(cmd)
    #         else:
    #             print("No resolution found in filename.")
    #     return str(out_playlist)