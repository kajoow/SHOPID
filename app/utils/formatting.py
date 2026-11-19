"""Helper formatting: format Rupiah dan konversi waktu Asia/Jakarta (Bab 6 & 11.5)."""
from datetime import datetime, timezone
import zoneinfo

JAKARTA_TZ = zoneinfo.ZoneInfo("Asia/Jakarta")


def format_rupiah(val: int | float | None) -> str:
    """Format angka integer ke string Rupiah (mis. Rp 52.200)."""
    if val is None:
        return "Rp 0"
    n = int(round(val))
    return f"Rp {n:,}".replace(",", ".")


def to_jakarta_time(dt: datetime | None) -> datetime | None:
    """Konversi waktu UTC ke zona waktu Asia/Jakarta."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(JAKARTA_TZ)


def format_datetime(dt: datetime | None, fmt: str = "%d %b %Y, %H:%M") -> str:
    """Format datetime UTC menjadi string lokal Asia/Jakarta."""
    if dt is None:
        return "-"
    jkt = to_jakarta_time(dt)
    return jkt.strftime(fmt)

