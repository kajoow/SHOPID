"""Report service: Analitik dan agregasi penjualan, inventori, dan dashboard admin (Bab 7.H, 14.6)."""
from datetime import datetime, timezone
from ..repositories import order_repo, product_repo
from ..models.enums import OrderStatus, PaymentStatus
from ..utils.formatting import format_rupiah


class ReportService:
    def get_dashboard_summary(self) -> dict:
        """Data real database untuk dashboard admin: KPI, order pending, dan stok rendah (Bab 7.H)."""
        # 1. Total penjualan selesai & jumlah order selesai (Bab 7.H & TC-RP-01)
        sales_pipeline = [
            {"$match": {"order_status": OrderStatus.COMPLETED}},
            {
                "$group": {
                    "_id": None,
                    "total_sales": {"$sum": "$total"},
                    "completed_count": {"$sum": 1},
                }
            },
        ]
        sales_res = order_repo.aggregate(sales_pipeline)
        total_sales = sales_res[0]["total_sales"] if sales_res else 0
        completed_orders_count = sales_res[0]["completed_count"] if sales_res else 0

        # 2. Antrean verifikasi pembayaran
        awaiting_count = order_repo.count({"payment_status": PaymentStatus.AWAITING_VERIFICATION})

        # 3. Jumlah produk stok rendah
        low_stock_pipeline = [
            {"$match": {"is_active": True, "$expr": {"$lte": ["$stock", "$min_stock"]}}},
            {"$count": "count"},
        ]
        low_res = product_repo.aggregate(low_stock_pipeline)
        low_stock_count = low_res[0]["count"] if low_res else 0

        # 4. Daftar order pending terkini
        pending_orders = order_repo.find_all(
            {"order_status": OrderStatus.PENDING},
            sort_list=[("created_at", -1)],
            skip=0,
            limit=5,
        )

        # 5. Daftar produk stok rendah terkini
        low_stock_products = product_repo.find_low_stock(limit=5)

        kpi = [
            ("Penjualan selesai", format_rupiah(total_sales)),
            ("Order selesai", completed_orders_count),
            ("Perlu verifikasi", awaiting_count),
            ("Stok rendah", low_stock_count),
        ]

        return {
            "kpi": kpi,
            "total_sales": total_sales,
            "completed_orders_count": completed_orders_count,
            "awaiting_count": awaiting_count,
            "low_stock_count": low_stock_count,
            "pending_orders": pending_orders,
            "low_stock": low_stock_products,
        }

    def get_sales_report(self, from_date: str | None = None, to_date: str | None = None) -> dict:
        """Laporan penjualan harian dengan zona waktu Asia/Jakarta dari order completed (Bab 7.H & TC-RP-01..02)."""
        match_criteria = {"order_status": OrderStatus.COMPLETED}

        date_match = {}
        if from_date and from_date.strip():
            try:
                date_match["$gte"] = datetime.strptime(from_date.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        if to_date and to_date.strip():
            try:
                date_match["$lte"] = datetime.strptime(to_date.strip(), "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
            except ValueError:
                pass

        if date_match:
            match_criteria["created_at"] = date_match

        pipeline = [
            {"$match": match_criteria},
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at",
                            "timezone": "Asia/Jakarta",
                        }
                    },
                    "total_sales": {"$sum": "$total"},
                    "order_count": {"$sum": 1},
                    "total_discount": {"$sum": "$discount"},
                    "total_delivery_fee": {"$sum": "$delivery_fee"},
                }
            },
            {"$sort": {"_id": 1}},
        ]

        daily_results = order_repo.aggregate(pipeline)

        grand_total_sales = 0
        grand_total_orders = 0
        formatted_daily = []

        for row in daily_results:
            grand_total_sales += row["total_sales"]
            grand_total_orders += row["order_count"]
            formatted_daily.append({
                "date": row["_id"],
                "total_sales": row["total_sales"],
                "order_count": row["order_count"],
                "total_discount": row.get("total_discount", 0),
                "total_delivery_fee": row.get("total_delivery_fee", 0),
            })

        return {
            "daily": formatted_daily,
            "grand_total_sales": grand_total_sales,
            "grand_total_orders": grand_total_orders,
            "from_date": from_date or "",
            "to_date": to_date or "",
        }

    def get_inventory_report(self) -> dict:
        """Status dan valuasi inventori dari database nyata master_product (Bab 7.H)."""
        pipeline = [
            {"$match": {"is_active": True}},
            {
                "$group": {
                    "_id": None,
                    "total_products": {"$sum": 1},
                    "total_stock_units": {"$sum": "$stock"},
                    "total_valuation": {"$sum": {"$multiply": ["$stock", "$price"]}},
                }
            },
        ]
        summary_res = product_repo.aggregate(pipeline)
        summary = summary_res[0] if summary_res else {
            "total_products": 0,
            "total_stock_units": 0,
            "total_valuation": 0,
        }

        # Daftar semua produk aktif diurutkan berdasarkan stok terkecil
        products = product_repo.find_all({"is_active": True}, sort_list=[("stock", 1), ("name", 1)], skip=0, limit=200)

        out_of_stock_count = sum(1 for p in products if p.get("stock", 0) == 0)
        low_stock_count = sum(1 for p in products if 0 < p.get("stock", 0) <= p.get("min_stock", 5))

        return {
            "total_products": summary.get("total_products", 0),
            "total_stock_units": summary.get("total_stock_units", 0),
            "total_valuation": summary.get("total_valuation", 0),
            "out_of_stock_count": out_of_stock_count,
            "low_stock_count": low_stock_count,
            "products": products,
        }


report_service = ReportService()

