"""Promotion service: Logika perhitungan dan validasi voucher diskon (Bab 7.G & 13.1)."""
import math
from datetime import datetime, timezone
from ..repositories import promotion_repo
from ..models.enums import DiscountType
from ..utils.validators import ValidationError


class PromotionService:
    def validate_and_calculate_discount(self, code: str | None, subtotal: int) -> tuple[int, dict | None]:
        """Validasi voucher dan hitung nilai diskon Rupiah (integer, floor) (Bab 7.G & 13.1)."""
        if not code or not str(code).strip():
            return 0, None

        clean_code = str(code).strip().upper()
        promo = promotion_repo.find_by_code(clean_code)
        if not promo:
            raise ValidationError(f"Kode voucher '{clean_code}' tidak ditemukan", field="voucher_code")

        if not promo.get("is_active", True):
            raise ValidationError(f"Voucher '{clean_code}' sudah tidak aktif", field="voucher_code")

        # Cek periode berlaku
        now = datetime.now(timezone.utc)
        starts_at = promo["starts_at"]
        ends_at = promo["ends_at"]
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)

        if now < starts_at:
            raise ValidationError(f"Voucher '{clean_code}' belum dapat digunakan", field="voucher_code")
        if now > ends_at:
            raise ValidationError(f"Voucher '{clean_code}' telah kedaluwarsa", field="voucher_code")

        # Cek kuota
        if promo.get("used_count", 0) >= promo.get("quota", 0):
            raise ValidationError(f"Kuota voucher '{clean_code}' telah habis", field="voucher_code")

        # Cek minimum belanja
        min_order = promo.get("min_order", 0)
        if subtotal < min_order:
            raise ValidationError(
                f"Voucher '{clean_code}' memerlukan minimal belanja Rp {min_order:,}".replace(",", "."),
                field="voucher_code",
            )

        # Hitung diskon (Bab 13.1)
        discount_type = promo.get("discount_type")
        val = promo.get("value", 0)

        if discount_type == DiscountType.FIXED:
            raw_discount = int(val)
        elif discount_type == DiscountType.PERCENTAGE:
            raw_discount = int(math.floor(subtotal * val / 100))
            max_disc = promo.get("max_discount")
            if max_disc is not None and max_disc > 0:
                raw_discount = min(raw_discount, max_disc)
        else:
            raw_discount = 0

        # Diskon tidak boleh melebihi subtotal
        final_discount = min(raw_discount, subtotal)
        return final_discount, promo


promotion_service = PromotionService()

