"""Product repository: Akses PyMongo untuk koleksi wajib master_product (Bab 12.3)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class ProductRepository:
    @property
    def collection(self):
        return get_db()["master_product"]

    def find_by_id(self, product_id: ObjectId | str) -> dict | None:
        if not isinstance(product_id, ObjectId):
            try:
                product_id = ObjectId(product_id)
            except Exception:
                return None
        return self.collection.find_one({"_id": product_id})

    def find_by_sku(self, sku: str) -> dict | None:
        return self.collection.find_one({"sku": sku.strip().upper()})

    def insert(
        self,
        sku: str,
        name: str,
        category_id: ObjectId,
        price: int,
        stock: int = 0,
        min_stock: int = 5,
        description: str | None = None,
        image_url: str | None = None,
        is_active: bool = True,
        session: ClientSession | None = None,
    ) -> ObjectId:
        now = datetime.now(timezone.utc)
        doc = {
            "sku": sku.strip().upper(),
            "name": name.strip(),
            "category_id": category_id,
            "description": description,
            "price": int(price),
            "stock": int(stock),
            "min_stock": int(min_stock),
            "sold_count": 0,
            "rating_avg": 0.0,
            "rating_count": 0,
            "image_url": image_url,
            "is_active": is_active,
            "created_at": now,
            "updated_at": now,
        }
        res = self.collection.insert_one(doc, session=session)
        return res.inserted_id

    def update(
        self,
        product_id: ObjectId,
        updates: dict,
        session: ClientSession | None = None,
    ) -> bool:
        updates["updated_at"] = datetime.now(timezone.utc)
        res = self.collection.update_one(
            {"_id": product_id},
            {"$set": updates},
            session=session,
        )
        return res.modified_count > 0

    def soft_delete(self, product_id: ObjectId, session: ClientSession | None = None) -> bool:
        """Soft delete: is_active=False (Bab 1.3 D4)."""
        return self.update(product_id, {"is_active": False}, session=session)

    def dec_stock_if_enough(
        self,
        product_id: ObjectId,
        qty: int,
        session: ClientSession | None = None,
    ):
        """Update atomik pengurangan stok bersyarat stock >= qty (Bab 11.4)."""
        now = datetime.now(timezone.utc)
        return self.collection.update_one(
            {"_id": product_id, "stock": {"$gte": qty}},
            {"$inc": {"stock": -qty}, "$set": {"updated_at": now}},
            session=session,
        )

    def inc_stock(
        self,
        product_id: ObjectId,
        qty: int,
        session: ClientSession | None = None,
    ):
        """Update atomik penambahan stok (restock/restoration)."""
        now = datetime.now(timezone.utc)
        return self.collection.update_one(
            {"_id": product_id},
            {"$inc": {"stock": qty}, "$set": {"updated_at": now}},
            session=session,
        )

    def set_stock(
        self,
        product_id: ObjectId,
        new_stock: int,
        session: ClientSession | None = None,
    ):
        """Update stok untuk koreksi opname (new_stock >= 0)."""
        now = datetime.now(timezone.utc)
        return self.collection.update_one(
            {"_id": product_id},
            {"$set": {"stock": new_stock, "updated_at": now}},
            session=session,
        )

    def inc_sold_count(
        self,
        product_id: ObjectId,
        qty: int,
        session: ClientSession | None = None,
    ):
        return self.collection.update_one(
            {"_id": product_id},
            {"$inc": {"sold_count": qty}},
            session=session,
        )

    def update_rating(
        self,
        product_id: ObjectId,
        rating_avg: float,
        rating_count: int,
        session: ClientSession | None = None,
    ):
        return self.collection.update_one(
            {"_id": product_id},
            {"$set": {"rating_avg": rating_avg, "rating_count": rating_count}},
            session=session,
        )

    def find_all(self, query: dict, sort_list: list, skip: int = 0, limit: int = 20):
        cursor = self.collection.find(query)
        if sort_list:
            cursor = cursor.sort(sort_list)
        return list(cursor.skip(skip).limit(limit))

    def count(self, query: dict) -> int:
        return self.collection.count_documents(query)

    def find_low_stock(self, limit: int = 20):
        """Produk dengan stock <= min_stock (Bab 13.1)."""
        pipeline = [
            {"$match": {"is_active": True, "$expr": {"$lte": ["$stock", "$min_stock"]}}},
            {"$sort": {"stock": 1}},
            {"$limit": limit},
        ]
        return list(self.collection.aggregate(pipeline))

    def aggregate(self, pipeline: list):
        return list(self.collection.aggregate(pipeline))


product_repo = ProductRepository()

