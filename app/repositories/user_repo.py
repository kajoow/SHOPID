"""User repository: Akses PyMongo untuk koleksi users (Bab 12.1)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class UserRepository:
    @property
    def collection(self):
        return get_db()["users"]

    def find_by_id(self, user_id: ObjectId | str) -> dict | None:
        if not isinstance(user_id, ObjectId):
            try:
                user_id = ObjectId(user_id)
            except Exception:
                return None
        return self.collection.find_one({"_id": user_id})

    def find_by_email(self, email: str) -> dict | None:
        return self.collection.find_one({"email": email.strip().lower()})

    def insert(
        self,
        name: str,
        email: str,
        password_hash: str,
        role: str = "user",
        phone: str | None = None,
        address: str | None = None,
        is_active: bool = True,
        session: ClientSession | None = None,
    ) -> ObjectId:
        doc = {
            "name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": password_hash,
            "role": role,
            "phone": phone,
            "address": address,
            "is_active": is_active,
            "created_at": datetime.now(timezone.utc),
        }
        res = self.collection.insert_one(doc, session=session)
        return res.inserted_id

    def update_profile(
        self,
        user_id: ObjectId,
        updates: dict,
        session: ClientSession | None = None,
    ) -> bool:
        res = self.collection.update_one(
            {"_id": user_id},
            {"$set": updates},
            session=session,
        )
        return res.modified_count > 0

    def update_password(
        self,
        user_id: ObjectId,
        password_hash: str,
        session: ClientSession | None = None,
    ) -> bool:
        res = self.collection.update_one(
            {"_id": user_id},
            {"$set": {"password_hash": password_hash}},
            session=session,
        )
        return res.modified_count > 0

    def find_all(self, query: dict, skip: int = 0, limit: int = 20):
        return list(
            self.collection.find(query)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

    def count(self, query: dict) -> int:
        return self.collection.count_documents(query)


user_repo = UserRepository()

