"""Audit repository: Satu-satunya tempat akses PyMongo untuk koleksi audit_logs (Bab 12.11)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class AuditRepository:
    def __init__(self):
        pass

    @property
    def collection(self):
        return get_db()["audit_logs"]

    def log(
        self,
        actor_id: ObjectId,
        action: str,
        entity_type: str,
        entity_id: ObjectId,
        before: dict | None = None,
        after: dict | None = None,
        session: ClientSession | None = None,
    ) -> ObjectId:
        doc = {
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "before": before,
            "after": after,
            "created_at": datetime.now(timezone.utc),
        }
        res = self.collection.insert_one(doc, session=session)
        return res.inserted_id

    def find_all(self, query: dict, skip: int = 0, limit: int = 20):
        return list(
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

    def count(self, query: dict) -> int:
        return self.collection.count_documents(query)


audit_repo = AuditRepository()

