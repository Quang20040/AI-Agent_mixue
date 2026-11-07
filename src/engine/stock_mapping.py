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
    'NL11': '23',  # Mứt xoài → Syrup Xoài (850g*20 lon) — shop confirmed: "mứt xoài là syrup xoài"
    'NL12': '17',  # Mứt đào mật (= đào hồng, dùng cho Super sundae đào hồng) → Mứt trái đào / syrup đào hồng (900g*20 hộp)
    'NL13': '16',  # Mứt đào vàng → Mứt đào vàng / syrup đào vàng (900g*20 hộp)
    'NL14': '24',  # Mứt dâu tây → Syrup Dâu Tây (900g*20 hộp) — shop confirmed
    'NL15': '27',  # Mứt chanh leo → Syrup chanh dây (chanh leo = chanh dây)
    'NL16': '15',  # Mứt cam bưởi → Syrup cam bưởi
}
# Not bought on their own, so never put on a purchase order (shop confirmed):
NOT_PURCHASED = {
    'NL09': 'lấy từ thùng ốc quế',          # Vụn ốc quế = broken cones from the cone carton
}
# Bought by the box outside the stock sheet (shop confirmed) — on-hand is not tracked in the ledger.
BOUGHT_PER_BOX = {'NL22'}                    # Bột cà phê hòa tan


def stock_id(recipe_id: str) -> str | None:
    return RECIPE_TO_STOCK.get(str(recipe_id))
