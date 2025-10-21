from dotenv import load_dotenv
import os

load_dotenv()

class Config:
    def __init__(self):
        # MinIO Repository
        self.minioHost = os.getenv("MINIO_HOST")
        self.minioPort = os.getenv("MINIO_PORT")
        self.minioPassword = os.getenv("MINIO_PASSWORD")
        self.minioUsername = os.getenv("MINIO_USERNAME")
        self.minioDirectory = os.getenv("MINIO_DIRECTORY")
        self.minioBucketName = os.getenv("MINIO_BUCKET_NAME")
        # Host
        self.host = os.getenv("HOST")
        self.port = os.getenv("PORT")
        # Directory
        self.outputPath = os.getenv("OUTPUT_DIRECTORY_PATH")
        self.renderdPath = os.getenv("RENDERED_DIRECTORY_PATH")

