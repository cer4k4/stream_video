import io
import re
import os
import logging
from minio import Minio
from minio.error import S3Error
from datetime import timedelta
from config.config import Config
from defualt_render_list import *

logger = logging.getLogger(__name__)

MIME_MAP = {
    ".mp4": "video/mp4",
    ".m3u8": "application/vnd.apple.mpegurl",
    ".ts": "video/mp2t",
    ".mpd": "application/dash+xml",
}

class MinIORepository:
    def __init__(self,bucket:str,directory:str):
        cfg = Config()
        self.connection = Minio(endpoint=f"{cfg.minioHost}:{cfg.minioPort}",access_key=cfg.minioUsername,secret_key=cfg.minioPassword,secure=False)
        self.bucket = bucket
        self.directory = directory

    def directory_exists(self) -> bool:
         """Check if a prefix (directory) exists in MinIO"""
         objects = self.connection.list_objects(self.bucket, self.directory, recursive=True)
         return any(True for _ in objects)

    def bucket_exists(self):
        found = self.connection.bucket_exists(bucket_name=self.bucket)
        if not found:
            self.connection.make_bucket(bucket_name=self.bucket)
            print("Created bucket", self.bucket)
        else:
            print("Bucket", self.bucket, "already exists")
            
    async def uploadFiles(self,files: list,filesPath: str):
        """Return True if any object starts with prefix (simulate directory existence)"""
        for o in files:
            if not self.directory_exists():
                data = io.BytesIO(b"")
                self.connection.put_object(self.bucket, self.directory, data, 0)
            else:
                self.connection.fput_object(self.bucket,object_name=o,file_path=filesPath+o)

    async def get_file_by_file_name(self,filename: str):
        # اگر پوشه ندارید، فقط نام فایل را استفاده کنید
        object_name = filename

        # بررسی وجود فایل (اختیاری)
        found = any(
            obj.object_name == object_name
            for obj in self.connection.list_objects(self.bucket, recursive=True)
        )

        if not found:
            print(f"⚠️ File not found in MinIO: {object_name}")
            return None

        # ایجاد لینک presigned با ۷ روز اعتبار
        url = self.connection.presigned_get_object(
            bucket_name=self.bucket,
            object_name=object_name,
            expires=timedelta(days=7)
        )
        print(f"✅ Presigned URL: {url}")
        return url
    

    def get_mime_type(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        return MIME_MAP.get(ext, "application/octet-stream")

    def parse_range_header(self, range_header: str | None, file_size: int) -> tuple[int, int] | None:
        if not range_header:
            return None

        match = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not match:
            return None

        start, end = match.groups()
        start = int(start) if start else 0
        end = int(end) if end else file_size - 1

        if start > end or end >= file_size:
            return None

        return start, end

    def get_stat(self, filename: str):
        """Get file metadata (size, etag, etc.)"""
        return self.connection.stat_object(self.bucket, filename)

    def get_file_stream(self, filename: str, range_header: str | None = None):
        """Return stream response info and headers"""
        try:
            stat = self.get_stat(filename)
            file_size = stat.size
            mime_type = self.get_mime_type(filename)
            byte_range = self.parse_range_header(range_header, file_size)

            if byte_range:
                start, end = byte_range
                length = end - start + 1
                range_str = f"bytes={start}-{end}"

                response = self.connection.get_object(
                    self.bucket,
                    filename,
                    request_headers={"Range": range_str},
                )

                headers = {
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(length),
                    "Content-Type": mime_type,
                }

                return response, headers, 206

            # full file
            response = self.connection.get_object(self.bucket, filename)
            return response, {"Content-Type": mime_type}, 200

        except S3Error as e:
            logger.error(f"MinIO error: {e}")
            raise FileNotFoundError(f"MinIO: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise FileNotFoundError("Error accessing file from MinIO")