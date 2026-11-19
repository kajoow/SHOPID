"""Keyword-based local illustrations for products without uploaded photos."""

PRODUCT_VISUALS = (
    (("air mineral", "air kemasan"), "water.svg"),
    (("deterjen", "detergent"), "detergent.svg"),
    (("kopi susu",), "coffee-can.svg"),
    (("susu",), "milk.svg"),
    (("teh botol",), "tea-bottle.svg"),
    (("teh",), "tea.svg"),
    (("biskuit", "gandum"), "biscuits.svg"),
    (("wafer",), "wafer.svg"),
    (("kacang",), "peanuts.svg"),
    (("makaroni",), "macaroni.svg"),
    (("sabun cuci piring",), "dish-soap.svg"),
    (("pembersih lantai",), "floor-cleaner.svg"),
    (("sampo", "shampoo"), "shampoo.svg"),
    (("deodoran", "deodorant"), "deodorant.svg"),
    (("sabun",), "body-wash.svg"),
    (("kopi",), "coffee.svg"),
    (("jus", "jeruk"), "juice.svg"),
    (("keripik",), "chips.svg"),
    (("tisu", "tissue"), "tissue.svg"),
    (("pasta gigi", "odol"), "toothpaste.svg"),
)


def product_image_for(name: str | None) -> str:
    normalized_name = (name or "").casefold()
    for keywords, image_name in PRODUCT_VISUALS:
        if any(keyword in normalized_name for keyword in keywords):
            return f"images/products/{image_name}"
    return "images/products/general.svg"
