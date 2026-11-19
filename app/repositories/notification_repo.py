"""Notification repository: Akses PyMongo untuk koleksi notifications (Bab 12.10)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class NotificationRepository:
    @property
    def collection(self):
        return get_db()["notifications"]

    def insert(
        self,
        user_id: ObjectId,
        title: str,
        message: str,
        notif_type: str,
        reference_id: ObjectId | None = None,
        session: ClientSession | None = None,
    ) -> ObjectId:
        doc = {
            "user_id": user_id,
            "title": title.strip(),
            "message": message.strip(),
            "type": notif_type,
            "is_read": False,
            "reference_id": reference_id,
            "created_at": datetime.now(timezone.utc),
        }
        res = self.collection.insert_one(doc, session=session)
        return res.inserted_id

    def find_by_user(self, user_id: ObjectId, skip: int = 0, limit: int = 20):
        return list(
            self.collection.find({"user_id": user_id})
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

    def mark_as_read(self, notif_id: ObjectId, user_id: ObjectId):
        return self.collection.update_one(
            {"_id": notif_id, "user_id": user_id},
            {"$set": {"is_read": True}},
        )

    def mark_all_as_read(self, user_id: ObjectId):
        return self.collection.update_many(
            {"user_id": user_id, "is_read": False},
            {"$set": {"is_read": True}},
        )

    def count_unread(self, user_id: ObjectId) -> int:
        return self.collection.count_documents({"user_id": user_id, "is_read": False})


notification_repo = NotificationRepository()

