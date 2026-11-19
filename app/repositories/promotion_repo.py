"""Promotion repository: Akses PyMongo untuk koleksi promotions (Bab 12.7)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class PromotionRepository:
    @property
    def collection(self):
        return get_db()["promotions"]

    def find_by_code(self, code: str) -> dict | None:
        return self.collection.find_one({"code": code.strip().upper()})

    def find_by_id(self, promo_id: ObjectId | str) -> dict | None:
        if not isinstance(promo_id, ObjectId):
            try:
                promo_id = ObjectId(promo_id)
            except Exception:
                return None
        return self.collection.find_one({"_id": promo_id})

    def insert(self, promo_doc: dict, session: ClientSession | None = None) -> ObjectId:
        promo_doc["code"] = promo_doc["code"].strip().upper()
        res = self.collection.insert_one(promo_doc, session=session)
        return res.inserted_id

    def update(self, promo_id: ObjectId, updates: dict, session: ClientSession | None = None) -> bool:
        res = self.collection.update_one({"_id": promo_id}, {"$set": updates}, session=session)
        return res.modified_count > 0

    def inc_used_if_quota(self, code: str, session: ClientSession | None = None):
        """Atomik menaikkan used_count hanya bila used_count < quota (Bab 13.3)."""
        return self.collection.update_one(
            {"code": code.strip().upper(), "$expr": {"$lt": ["$used_count", "$quota"]}},
            {"$inc": {"used_count": 1}},
            session=session,
        )

    def dec_used_count(self, code: str, session: ClientSession | None = None):
        """Mengurangi used_count saat order dibatalkan (Bab 1.3 D3)."""
        return self.collection.update_one(
            {"code": code.strip().upper(), "used_count": {"$gt": 0}},
            {"$inc": {"used_count": -1}},
            session=session,
        )

    def find_all(self, query: dict | None = None, skip: int = 0, limit: int = 20):
        q = query or {}
        return list(
            self.collection.find(q)
            .sort("starts_at", -1)
            .skip(skip)
            .limit(limit)
        )

    def count(self, query: dict | None = None) -> int:
        return self.collection.count_documents(query or {})


promotion_repo = PromotionRepository()

