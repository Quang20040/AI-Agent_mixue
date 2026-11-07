"""Recipe ingredient codes (NLxx, used in the recipes) → items of the stock sheet (numeric ids, bought in cartons).

The recipes and the stock sheet were digitised from different documents and use different codes. Only pairs that
are clearly the same product are listed; anything not listed is shown to the manager as "chưa ghép với sổ kho"
instead of being guessed. Add a pair here (and a test) once the shop confirms it.
"""
RECIPE_TO_STOCK = {
    'NL01': '10',  # Đường mật → Đường mật (đường mía) 6.5kg/bình, 4 bình/kiện
    'NL02': '9',   # Đường quả → Đường quả (Syrup hoa quả) 6.5kg/bình, 4 bình/kiện
    'NL03': '11',  # Syrup đường đen → Đường đen (1,2kg*12 chai)
    'NL04': '21',  # Syrup hạt dẻ và bơ → Syrup hạt dẻ
    'NL05': '25',  # Syrup socola → Syrup Socola
    'NL10': '29',  # Vụn Oreo → Vụn Oreo
    'NL13': '16',  # Mứt đào vàng → Mứt đào vàng (900g*20 hộp)
    'NL15': '27',  # Mứt chanh leo → Syrup chanh dây (chanh leo = chanh dây)
    'NL16': '15',  # Mứt cam bưởi → Syrup cam bưởi
}
# Still to confirm with the shop (left unmapped on purpose):
#   NL11 Mứt xoài ↔ 23 Syrup Xoài (lon)?   NL12 Mứt đào mật ↔ 17 Mứt trái đào?   NL14 Mứt dâu tây ↔ 24 Syrup Dâu Tây (hộp)?
#   NL09 Vụn ốc quế, NL22 Bột cà phê hòa tan: no matching stock item.


def stock_id(recipe_id: str) -> str | None:
    return RECIPE_TO_STOCK.get(str(recipe_id))
