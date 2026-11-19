"""Category repository: Akses PyMongo untuk koleksi categories (Bab 12.2)."""
from bson import ObjectId
from pymongo.client_session import ClientSession
from ..extensions import get_db


class CategoryRepository:
    @property
    def collection(self):
        return get_db()["categories"]

    def find_all(self, query: dict | None = None, sort_by: str = "name", ascending: bool = True):
        q = query or {}
        order = 1 if ascending else -1
        return list(self.collection.find(q).sort(sort_by, order))

    def find_by_id(self, cat_id: ObjectId | str) -> dict | None:
        if not isinstance(cat_id, ObjectId):
            try:
                cat_id = ObjectId(cat_id)
            except Exception:
                return None
        return self.collection.find_one({"_id": cat_id})

    def find_by_slug(self, slug: str) -> dict | None:
        return self.collection.find_one({"slug": slug.strip().lower()})

    def insert(
        self,
        name: str,
        slug: str,
        description: str | None = None,
        is_active: bool = True,
        session: ClientSession | None = None,
    ) -> ObjectId:
        doc = {
            "name": name.strip(),
            "slug": slug.strip().lower(),
            "description": description,
            "is_active": is_active,
        }
        res = self.collection.insert_one(doc, session=session)
        return res.inserted_id

    def update(self, cat_id: ObjectId, updates: dict, session: ClientSession | None = None) -> bool:
        res = self.collection.update_one({"_id": cat_id}, {"$set": updates}, session=session)
        return res.modified_count > 0

    def count(self, query: dict | None = None) -> int:
        return self.collection.count_documents(query or {})


category_repo = CategoryRepository()

