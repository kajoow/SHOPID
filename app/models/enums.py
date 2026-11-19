"""Definisi konstanta Enum sesuai Blueprint Bab 7 dan 12."""

class UserRole:
    USER = "user"
    ADMIN = "admin"
    ALL = [USER, ADMIN]


class OrderStatus:
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    READY_FOR_PICKUP = "ready_for_pickup"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ALL = [PENDING, CONFIRMED, PROCESSING, READY_FOR_PICKUP, COMPLETED, CANCELLED]
    TERMINAL = [COMPLETED, CANCELLED]


class PaymentStatus:
    UNPAID = "unpaid"
    AWAITING_VERIFICATION = "awaiting_verification"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    ALL = [UNPAID, AWAITING_VERIFICATION, PAID, FAILED, REFUNDED]


class FulfillmentMethod:
    PICKUP = "pickup"
    DELIVERY = "delivery"
    ALL = [PICKUP, DELIVERY]


class PaymentMethod:
    COD = "cod"
    BANK_TRANSFER = "bank_transfer"
    ALL = [COD, BANK_TRANSFER]


class StockMovementType:
    INITIAL = "initial"
    ADDITION = "addition"
    REDUCTION = "reduction"
    CORRECTION = "correction"
    RESTORATION = "restoration"
    ALL = [INITIAL, ADDITION, REDUCTION, CORRECTION, RESTORATION]


class StockReferenceType:
    ORDER = "order"
    MANUAL = "manual"
    PRODUCT_CREATE = "product_create"
    STOCKTAKE = "stocktake"
    ALL = [ORDER, MANUAL, PRODUCT_CREATE, STOCKTAKE]


class DiscountType:
    FIXED = "fixed"
    PERCENTAGE = "percentage"
    ALL = [FIXED, PERCENTAGE]


class NotificationType:
    ORDER_STATUS = "order_status"
    PAYMENT = "payment"
    LOW_STOCK = "low_stock"
    SYSTEM = "system"
    ALL = [ORDER_STATUS, PAYMENT, LOW_STOCK, SYSTEM]

