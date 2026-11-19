import pytest

from app.utils.product_images import product_image_for


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Air Mineral 600 ml", "images/products/water.svg"),
        ("Kopi Instan 100 g", "images/products/coffee.svg"),
        ("Jus Jeruk 1 L", "images/products/juice.svg"),
        ("Keripik Singkong Balado 160 g", "images/products/chips.svg"),
        ("Pasta Gigi Herbal 120 g", "images/products/toothpaste.svg"),
        ("Kopi Susu Kaleng 240 ml", "images/products/coffee-can.svg"),
        ("Susu UHT 1 L", "images/products/milk.svg"),
        ("Teh Botol 350 ml", "images/products/tea-bottle.svg"),
        ("Wafer Cokelat 150 g", "images/products/wafer.svg"),
        ("Kacang Panggang 100 g", "images/products/peanuts.svg"),
        ("Makaroni Pedas 120 g", "images/products/macaroni.svg"),
        ("Sabun Cuci Piring 700 ml", "images/products/dish-soap.svg"),
        ("Pembersih Lantai 800 ml", "images/products/floor-cleaner.svg"),
        ("Sampo Anti Ketombe 170 ml", "images/products/shampoo.svg"),
        ("Deodoran Roll On 50 ml", "images/products/deodorant.svg"),
    ],
)
def test_product_image_uses_matching_keyword(name, expected):
    assert product_image_for(name) == expected


def test_product_image_uses_generic_art_for_unknown_names():
    assert product_image_for("Produk tanpa kategori") == "images/products/general.svg"
    assert product_image_for(None) == "images/products/general.svg"
