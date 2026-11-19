"""Review repository: Akses PyMongo untuk koleksi reviews (Bab 12.9)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class ReviewRepository:
    @property
    def collection(self):
        return get_db()["reviews"]

    def insert(
        self,
        user_id: ObjectId,
        product_id: ObjectId,
        order_id: ObjectId,
        rating: int,
        comment: str | None = None,
        is_visible: bool = True,
        session: ClientSession | None = None,
    ) -> ObjectId:
        doc = {
            "user_id": user_id,
            "product_id": product_id,
            "order_id": order_id,
            "rating": int(rating),
            "comment": comment,
            "is_visible": is_visible,
            "created_at": datetime.now(timezone.utc),
        }
        res = self.collection.insert_one(doc, session=session)
        return res.inserted_id

    def find_by_product(self, product_id: ObjectId, only_visible: bool = True, skip: int = 0, limit: int = 20):
        q = {"product_id": product_id}
        if only_visible:
            q["is_visible"] = True
        return list(
            self.collection.find(q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

    def find_all(self, query: dict | None = None, skip: int = 0, limit: int = 20):
        q = query or {}
        return list(
            self.collection.find(q)
            .sort("created_at", -1)
            .skip(skip)
            .limit(limit)
        )

    def count(self, query: dict | None = None) -> int:
        return self.collection.count_documents(query or {})

    def set_visibility(self, review_id: ObjectId, is_visible: bool, session: ClientSession | None = None):
        return self.collection.update_one(
            {"_id": review_id},
            {"$set": {"is_visible": is_visible}},
            session=session,
        )

    def find_by_id(self, review_id: ObjectId | str) -> dict | None:
        if not isinstance(review_id, ObjectId):
            try:
                review_id = ObjectId(review_id)
            except Exception:
                return None
        return self.collection.find_one({"_id": review_id})

    def calculate_product_rating(self, product_id: ObjectId):
        """Hitung agregasi rating rata-rata produk untuk review yang visible."""
        pipeline = [
            {"$match": {"product_id": product_id, "is_visible": True}},
            {
                "$group": {
                    "_id": "$product_id",
                    "rating_avg": {"$avg": "$rating"},
                    "rating_count": {"$sum": 1},
                }
            },
        ]
        res = list(self.collection.aggregate(pipeline))
        if res:
            return round(res[0]["rating_avg"], 1), res[0]["rating_count"]
        return 0.0, 0


review_repo = ReviewRepository()

