"""Stock movement repository: Akses PyMongo untuk koleksi append-only stock_movements (Bab 12.6)."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db
from ..models.enums import StockMovementType, StockReferenceType


class StockRepository:
    @property
    def collection(self):
        return get_db()["stock_movements"]

    def insert(
        self,
        product_id: ObjectId,
        movement_type: str,
        quantity: int,
        before_stock: int,
        after_stock: int,
        reference_type: str,
        actor_id: ObjectId,
        reference_id: ObjectId | None = None,
        note: str | None = None,
        session: ClientSession | None = None,
    ) -> ObjectId:
        # Pengecekan invarian: after = before + quantity dan after >= 0 (Bab 12.6)
        if after_stock != before_stock + quantity:
            raise ValueError(f"Invarian gagal: after ({after_stock}) != before ({before_stock}) + quantity ({quantity})")
        if after_stock < 0 or before_stock < 0:
            raise ValueError("Stok tidak boleh negatif")

        doc = {
            "product_id": product_id,
            "movement_type": movement_type,
            "quantity": int(quantity),
            "before_stock": int(before_stock),
            "after_stock": int(after_stock),
            "reference_type": reference_type,
            "reference_id": reference_id,
            "actor_id": actor_id,
            "note": note,
            "created_at": datetime.now(timezone.utc),
        }
        res = self.collection.insert_one(doc, session=session)
        return res.inserted_id

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


stock_repo = StockRepository()

