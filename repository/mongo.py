from config.config import Config
from motor.motor_asyncio import AsyncIOMotorClient

class MongoRepository:
    def __init__(self):
        cfg = Config()
        self.client = AsyncIOMotorClient(f"mongodb://{cfg.mongoHost}:{cfg.mongoPort}/")
        self.db = self.client[cfg.mongoDatabase]
        self.collection = self.db["upload_status"]

    async def insert_status(self, filename: str, status: str,drm: dict):
        """Insert a new upload record"""
        doc = {"filename": filename, "status": status,"password":drm.get('key'),"key_uuid":drm.get('key_id')}
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def update_status(self, filename: str, status: str):
        """Update status by filename"""
        return await self.collection.update_one({"filename": filename},{"$set": {"status": status}},upsert=True)

    async def get_status(self, filename: str):
        """Fetch file upload status"""
        return await self.collection.find_one({"filename": filename})
