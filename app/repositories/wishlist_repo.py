"""Wishlist repository: Akses PyMongo untuk koleksi wishlists (Bab 12.8)."""
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class WishlistRepository:
    @property
    def collection(self):
        return get_db()["wishlists"]

    def find_by_user_id(self, user_id: ObjectId) -> dict | None:
        return self.collection.find_one({"user_id": user_id})

    def add_item(self, user_id: ObjectId, product_id: ObjectId, session: ClientSession | None = None):
        return self.collection.update_one(
            {"user_id": user_id},
            {"$addToSet": {"product_ids": product_id}},
            upsert=True,
            session=session,
        )

    def remove_item(self, user_id: ObjectId, product_id: ObjectId, session: ClientSession | None = None):
        return self.collection.update_one(
            {"user_id": user_id},
            {"$pull": {"product_ids": product_id}},
            session=session,
        )


wishlist_repo = WishlistRepository()

