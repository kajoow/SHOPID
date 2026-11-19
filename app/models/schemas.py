"""Definisi skema validasi $jsonSchema untuk 11 koleksi MongoDB (Bab 11 & 12)."""
from .enums import (
    UserRole,
    OrderStatus,
    PaymentStatus,
    FulfillmentMethod,
    PaymentMethod,
    StockMovementType,
    StockReferenceType,
    DiscountType,
    NotificationType,
)

COLLECTIONS = {
    "users": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["name", "email", "password_hash", "role", "is_active", "created_at"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "name": {"bsonType": "string", "minLength": 2, "maxLength": 100},
                "email": {"bsonType": "string", "maxLength": 254},
                "password_hash": {"bsonType": "string"},
                "role": {"enum": UserRole.ALL},
                "phone": {"bsonType": ["string", "null"]},
                "address": {"bsonType": ["string", "null"], "maxLength": 300},
                "profile_image": {"bsonType": ["string", "null"]},
                "is_active": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
    "categories": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["name", "slug", "is_active"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "name": {"bsonType": "string", "minLength": 2, "maxLength": 60},
                "slug": {"bsonType": "string"},
                "description": {"bsonType": ["string", "null"], "maxLength": 300},
                "is_active": {"bsonType": "bool"},
            },
            "additionalProperties": False,
        }
    },
    "master_product": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "sku", "name", "category_id", "price", "stock", "min_stock",
                "sold_count", "rating_avg", "rating_count", "is_active",
                "created_at", "updated_at"
            ],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "sku": {"bsonType": "string", "minLength": 3, "maxLength": 32},
                "name": {"bsonType": "string", "minLength": 2, "maxLength": 150},
                "category_id": {"bsonType": "objectId"},
                "description": {"bsonType": ["string", "null"], "maxLength": 2000},
                "price": {"bsonType": ["int", "long"], "minimum": 0},
                "stock": {"bsonType": ["int", "long"], "minimum": 0},
                "min_stock": {"bsonType": ["int", "long"], "minimum": 0},
                "sold_count": {"bsonType": ["int", "long"], "minimum": 0},
                "rating_avg": {"bsonType": ["double", "int", "long", "decimal"], "minimum": 0, "maximum": 5},
                "rating_count": {"bsonType": ["int", "long"], "minimum": 0},
                "image_url": {"bsonType": ["string", "null"]},
                "is_active": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
    "carts": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "items", "updated_at"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "user_id": {"bsonType": "objectId"},
                "items": {
                    "bsonType": "array",
                    "maxItems": 50,
                    "items": {
                        "bsonType": "object",
                        "required": ["product_id", "quantity", "added_at"],
                        "properties": {
                            "product_id": {"bsonType": "objectId"},
                            "quantity": {"bsonType": ["int", "long"], "minimum": 1, "maximum": 99},
                            "added_at": {"bsonType": "date"},
                        },
                        "additionalProperties": False,
                    },
                },
                "updated_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
    "orders": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "order_number", "user_id", "items", "subtotal", "discount",
                "delivery_fee", "total", "fulfillment_method", "payment_method",
                "payment_status", "order_status", "contact", "status_history",
                "idempotency_key", "created_at", "updated_at"
            ],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "order_number": {"bsonType": "string"},
                "user_id": {"bsonType": "objectId"},
                "items": {
                    "bsonType": "array",
                    "minItems": 1,
                    "maxItems": 50,
                    "items": {
                        "bsonType": "object",
                        "required": ["product_id", "sku", "name", "unit_price", "quantity", "line_total"],
                        "properties": {
                            "product_id": {"bsonType": "objectId"},
                            "sku": {"bsonType": "string"},
                            "name": {"bsonType": "string"},
                            "unit_price": {"bsonType": ["int", "long"], "minimum": 0},
                            "quantity": {"bsonType": ["int", "long"], "minimum": 1},
                            "line_total": {"bsonType": ["int", "long"], "minimum": 0},
                        },
                        "additionalProperties": False,
                    },
                },
                "subtotal": {"bsonType": ["int", "long"], "minimum": 0},
                "discount": {"bsonType": ["int", "long"], "minimum": 0},
                "delivery_fee": {"bsonType": ["int", "long"], "minimum": 0},
                "total": {"bsonType": ["int", "long"], "minimum": 0},
                "fulfillment_method": {"enum": FulfillmentMethod.ALL},
                "payment_method": {"enum": PaymentMethod.ALL},
                "payment_status": {"enum": PaymentStatus.ALL},
                "order_status": {"enum": OrderStatus.ALL},
                "contact": {
                    "bsonType": "object",
                    "required": ["name", "phone"],
                    "properties": {
                        "name": {"bsonType": "string", "minLength": 2, "maxLength": 100},
                        "phone": {"bsonType": "string"},
                    },
                    "additionalProperties": False,
                },
                "shipping_address": {
                    "bsonType": ["object", "null"],
                    "properties": {
                        "recipient": {"bsonType": ["string", "null"]},
                        "line": {"bsonType": "string", "maxLength": 300},
                        "city": {"bsonType": ["string", "null"]},
                        "postal_code": {"bsonType": ["string", "null"]},
                        "notes": {"bsonType": ["string", "null"]},
                    },
                    "additionalProperties": True,
                },
                "voucher_code": {"bsonType": ["string", "null"]},
                "payment_proof": {"bsonType": ["string", "null"]},
                "status_history": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["to", "actor_id", "at"],
                        "properties": {
                            "from": {"bsonType": ["string", "null"]},
                            "to": {"bsonType": "string"},
                            "actor_id": {"bsonType": "objectId"},
                            "at": {"bsonType": "date"},
                            "note": {"bsonType": ["string", "null"]},
                        },
                        "additionalProperties": False,
                    },
                },
                "idempotency_key": {"bsonType": "string"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
    "stock_movements": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "product_id", "movement_type", "quantity", "before_stock",
                "after_stock", "reference_type", "actor_id", "created_at"
            ],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "product_id": {"bsonType": "objectId"},
                "movement_type": {"enum": StockMovementType.ALL},
                "quantity": {"bsonType": ["int", "long"]},
                "before_stock": {"bsonType": ["int", "long"], "minimum": 0},
                "after_stock": {"bsonType": ["int", "long"], "minimum": 0},
                "reference_type": {"enum": StockReferenceType.ALL},
                "reference_id": {"bsonType": ["objectId", "null"]},
                "actor_id": {"bsonType": "objectId"},
                "note": {"bsonType": ["string", "null"], "maxLength": 200},
                "created_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
    "promotions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["code", "discount_type", "value", "min_order", "quota", "used_count", "starts_at", "ends_at", "is_active"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "code": {"bsonType": "string", "minLength": 4, "maxLength": 20},
                "discount_type": {"enum": DiscountType.ALL},
                "value": {"bsonType": ["double", "int", "long", "decimal"]},
                "min_order": {"bsonType": ["int", "long"], "minimum": 0},
                "max_discount": {"bsonType": ["int", "long", "null"]},
                "quota": {"bsonType": ["int", "long"], "minimum": 1},
                "used_count": {"bsonType": ["int", "long"], "minimum": 0},
                "starts_at": {"bsonType": "date"},
                "ends_at": {"bsonType": "date"},
                "is_active": {"bsonType": "bool"},
            },
            "additionalProperties": False,
        }
    },
    "wishlists": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "product_ids"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "user_id": {"bsonType": "objectId"},
                "product_ids": {
                    "bsonType": "array",
                    "maxItems": 200,
                    "items": {"bsonType": "objectId"},
                },
            },
            "additionalProperties": False,
        }
    },
    "reviews": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "product_id", "order_id", "rating", "is_visible", "created_at"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "user_id": {"bsonType": "objectId"},
                "product_id": {"bsonType": "objectId"},
                "order_id": {"bsonType": "objectId"},
                "rating": {"bsonType": ["int", "long"], "minimum": 1, "maximum": 5},
                "comment": {"bsonType": ["string", "null"], "maxLength": 1000},
                "is_visible": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
    "notifications": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["user_id", "title", "message", "type", "is_read", "created_at"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "user_id": {"bsonType": "objectId"},
                "title": {"bsonType": "string", "minLength": 1, "maxLength": 100},
                "message": {"bsonType": "string", "minLength": 1, "maxLength": 500},
                "type": {"enum": NotificationType.ALL},
                "is_read": {"bsonType": "bool"},
                "reference_id": {"bsonType": ["objectId", "null"]},
                "created_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
    "audit_logs": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["actor_id", "action", "entity_type", "entity_id", "created_at"],
            "properties": {
                "_id": {"bsonType": "objectId"},
                "actor_id": {"bsonType": "objectId"},
                "action": {"bsonType": "string"},
                "entity_type": {"bsonType": "string"},
                "entity_id": {"bsonType": "objectId"},
                "before": {"bsonType": ["object", "null"]},
                "after": {"bsonType": ["object", "null"]},
                "created_at": {"bsonType": "date"},
            },
            "additionalProperties": False,
        }
    },
}

