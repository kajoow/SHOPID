"""Order repository: Akses PyMongo untuk koleksi orders (Bab 12.5)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class OrderRepository:
    @property
    def collection(self):
        return get_db()["orders"]

    def find_by_id(self, order_id: ObjectId | str) -> dict | None:
        if not isinstance(order_id, ObjectId):
            try:
                order_id = ObjectId(order_id)
            except Exception:
                return None
        return self.collection.find_one({"_id": order_id})

    def find_by_order_number(self, order_number: str) -> dict | None:
        return self.collection.find_one({"order_number": order_number.strip()})

    def find_by_idempotency_key(self, idempotency_key: str) -> dict | None:
        return self.collection.find_one({"idempotency_key": idempotency_key.strip()})

    def insert(self, order_doc: dict, session: ClientSession | None = None) -> ObjectId:
        now = datetime.now(timezone.utc)
        if "created_at" not in order_doc:
            order_doc["created_at"] = now
        if "updated_at" not in order_doc:
            order_doc["updated_at"] = now
        res = self.collection.insert_one(order_doc, session=session)
        return res.inserted_id

    def update_status_conditional(
        self,
        order_id: ObjectId,
        from_status: str,
        to_status: str,
        actor_id: ObjectId,
        note: str | None = None,
        session: ClientSession | None = None,
    ):
        """Update transisi order_status bersyarat {_id, order_status: <asal>} (Bab 11.4)."""
        now = datetime.now(timezone.utc)
        history_entry = {
            "from": from_status,
            "to": to_status,
            "actor_id": actor_id,
            "at": now,
            "note": note,
        }
        return self.collection.update_one(
            {"_id": order_id, "order_status": from_status},
            {
                "$set": {"order_status": to_status, "updated_at": now},
                "$push": {"status_history": history_entry},
            },
            session=session,
        )

    def update_payment_status(
        self,
        order_id: ObjectId,
        payment_status: str,
        actor_id: ObjectId | None = None,
        note: str | None = None,
        session: ClientSession | None = None,
    ):
        now = datetime.now(timezone.utc)
        update_doc = {"$set": {"payment_status": payment_status, "updated_at": now}}
        if actor_id:
            update_doc["$push"] = {
                "status_history": {
                    "from": None,
                    "to": f"payment:{payment_status}",
                    "actor_id": actor_id,
                    "at": now,
                    "note": note,
                }
            }
        return self.collection.update_one({"_id": order_id}, update_doc, session=session)

    def set_payment_proof(
        self,
        order_id: ObjectId,
        proof_path: str,
        session: ClientSession | None = None,
    ):
        now = datetime.now(timezone.utc)
        return self.collection.update_one(
            {"_id": order_id},
            {
                "$set": {
                    "payment_proof": proof_path,
                    "payment_status": "awaiting_verification",
                    "updated_at": now,
                }
            },
            session=session,
        )

    def find_all(self, query: dict, sort_list: list | None = None, skip: int = 0, limit: int = 20):
        sort_criteria = sort_list or [("created_at", -1)]
        return list(
            self.collection.find(query)
            .sort(sort_criteria)
            .skip(skip)
            .limit(limit)
        )

    def count(self, query: dict) -> int:
        return self.collection.count_documents(query)

    def aggregate(self, pipeline: list):
        return list(self.collection.aggregate(pipeline))


order_repo = OrderRepository()

