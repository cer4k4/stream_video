import io
from minio import Minio
from config.config import Config
from defualt_render_list import *


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
                self.connection.fput_object(self.bucket,object_name=self.directory+o,file_path=filesPath+o)
