"""Cart repository: Akses PyMongo untuk koleksi carts (Bab 12.4)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class CartRepository:
    @property
    def collection(self):
        return get_db()["carts"]

    def find_by_user_id(self, user_id: ObjectId) -> dict | None:
        return self.collection.find_one({"user_id": user_id})

    def ensure_cart(self, user_id: ObjectId, session: ClientSession | None = None) -> dict:
        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"user_id": user_id},
            {"$setOnInsert": {"user_id": user_id, "items": [], "updated_at": now}},
            upsert=True,
            session=session,
        )
        return self.find_by_user_id(user_id)

    def add_or_update_item(
        self,
        user_id: ObjectId,
        product_id: ObjectId,
        quantity: int,
        session: ClientSession | None = None,
    ):
        now = datetime.now(timezone.utc)
        cart = self.collection.find_one({"user_id": user_id}, session=session)
        if not cart:
            cart_doc = {
                "user_id": user_id,
                "items": [{"product_id": product_id, "quantity": quantity, "added_at": now}],
                "updated_at": now,
            }
            self.collection.insert_one(cart_doc, session=session)
            return

        # Cari apakah item sudah ada
        items = cart.get("items", [])
        found = False
        for item in items:
            if item["product_id"] == product_id:
                item["quantity"] += quantity
                item["added_at"] = now
                found = True
                break

        if not found:
            items.append({"product_id": product_id, "quantity": quantity, "added_at": now})

        self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"items": items, "updated_at": now}},
            session=session,
        )

    def set_item_quantity(
        self,
        user_id: ObjectId,
        product_id: ObjectId,
        quantity: int,
        session: ClientSession | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        res = self.collection.update_one(
            {"user_id": user_id, "items.product_id": product_id},
            {"$set": {"items.$.quantity": quantity, "updated_at": now}},
            session=session,
        )
        return res.modified_count > 0

    def remove_item(
        self,
        user_id: ObjectId,
        product_id: ObjectId,
        session: ClientSession | None = None,
    ) -> bool:
        now = datetime.now(timezone.utc)
        res = self.collection.update_one(
            {"user_id": user_id},
            {"$pull": {"items": {"product_id": product_id}}, "$set": {"updated_at": now}},
            session=session,
        )
        return res.modified_count > 0

    def clear(self, user_id: ObjectId, session: ClientSession | None = None):
        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"user_id": user_id},
            {"$set": {"items": [], "updated_at": now}},
            session=session,
        )

    def get_cart_count(self, user_id: ObjectId) -> int:
        cart = self.collection.find_one({"user_id": user_id}, {"items": 1})
        if not cart or "items" not in cart:
            return 0
        return sum(item.get("quantity", 0) for item in cart["items"])


cart_repo = CartRepository()

