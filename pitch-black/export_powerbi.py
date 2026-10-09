#!/usr/bin/env python3
"""Flatten the daily Pitch Black checker state into CSVs for the PKMN Collection Value Power BI report.

Usage: python3 export_powerbi.py <pitch_black_cloud_state.json> <out_dir>
Writes pb_run.csv, pb_cards.csv and pb_listings.csv. The report reads them from
raw.githubusercontent.com/kkarageorge/pkmn-tcg/main/pitch-black/data/ on its daily refresh.
Postage follows the checker's rules: Fetch $6.00 tracked per seller unless known, stores $10.00 per order,
eBay the listing's own shipping. Standard library only (runs in the cloud routine).
"""
import csv, json, os, sys

DEFAULT_POST, STORE_POST = 6.00, 10.00
POSTAGE = {"offthecuff_collects": 2.80, "Tango": 6.50}
IMG = {"mpb": 4687, "mcr": 4657}
SETS = {"mpb": "Pitch Black", "mcr": "Chaos Rising"}
STORE_URL = {"Good Games": "https://tcg.goodgames.com.au/search?q={q}", "Gameology": "https://www.gameology.com.au/search?q={q}"}


def num(cid):  # poke_mpb-116:084_SIR_standard_holo -> 116/084
    return cid.split("-", 1)[1].split("_")[0].replace(":", "/")


def rarity(cid):
    return {"SIR": "Special Illustration Rare", "MHR": "Mega Hyper Rare", "UR": "Ultra Rare", "IR": "Illustration Rare",
            "R": "Rare", "C": "Common", "U": "Uncommon"}.get(cid.split("_")[2], cid.split("_")[2])


def main(state_path, out):
    s = json.load(open(state_path, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    basket = s.get("basket") or {}
    choice, bpost = basket.get("choice") or {}, basket.get("post") or {}
    deals = set(s.get("deal_ids") or [])
    cards, rows = [], []
    for cid, c in (s.get("cards") or {}).items():
        key = cid.split("_")[1].split("-")[0]
        name = c["name"].rsplit(" ", 1)[0] if c["name"].split()[-1].isdigit() else c["name"]
        pick = choice.get(cid) or [None, None, None]
        cards.append(dict(card_id=cid, card=name, number=num(cid), set=SETS.get(key, c.get("set", "")), rarity=rarity(cid),
                          market=c.get("market") or "", fetch_sold_30d=c.get("sold") or "", fetch_sales_30d=c.get("sold_n") or 0,
                          image=f"https://card-images.fetchtcg.com/poke/{IMG.get(key, 4687)}/large/{cid}.png",
                          fetch_url=f"https://www.fetchtcg.com/cards/{cid}",
                          basket_source=("eBay AU" if (pick[0] or "").startswith("eBay ") else "Fetch") if pick[0] else "",
                          basket_seller=(pick[0] or "").replace("eBay ", "", 1), basket_price=pick[1] if pick[1] is not None else "",
                          basket_listing=pick[2] or ""))
        q = f"{name} {num(cid)}".replace(" ", "+").replace("/", "%2F")
        for lid, l in (c.get("listings") or {}).items():
            ebay = lid.startswith("ebay:")
            item = l.get("item", l["price"]) if ebay else l["price"]
            post = l.get("ship", 0.0) if ebay else POSTAGE.get(l["seller"], DEFAULT_POST)
            rows.append(dict(card_id=cid, listing_id=lid, source="eBay AU" if ebay else "Fetch",
                             seller=l["seller"].replace("eBay ", "", 1) if ebay else l["seller"],
                             item_price=round(item, 2), postage=round(post or 0, 2), landed=round(item + (post or 0), 2),
                             listed_at=l.get("listedAt") or "",
                             url=l.get("url", "").split("?")[0] if ebay else f"https://www.fetchtcg.com/cards/{cid}",
                             deal="Yes" if lid in deals else "", in_basket="Yes" if lid == pick[2] else ""))
        for store, price in ((s.get("stores") or {}).get(cid) or {}).items():
            rows.append(dict(card_id=cid, listing_id=f"store:{store}", source=store, seller=store, item_price=price,
                             postage=STORE_POST, landed=round(price + STORE_POST, 2), listed_at="",
                             url=STORE_URL.get(store, "").format(q=q), deal="", in_basket=""))
    run = dict(run=s.get("run", "")[:16].replace("T", " "), basket_total=basket.get("total", ""),
               basket_postage=round(sum(bpost.values()), 2), parcels=basket.get("parcels", ""),
               cards_needed=len(cards), cards_priced=basket.get("cards", ""), deals=len(deals))

    def write(name, data, cols):
        with open(os.path.join(out, name), "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, cols)
            w.writeheader()
            w.writerows(data)

    write("pb_run.csv", [run], list(run))
    write("pb_cards.csv", cards, list(cards[0]) if cards else ["card_id"])
    write("pb_listings.csv", sorted(rows, key=lambda r: (r["card_id"], r["landed"])),
          ["card_id", "listing_id", "source", "seller", "item_price", "postage", "landed", "listed_at", "url", "deal", "in_basket"])
    print(f"powerbi: {len(cards)} cards, {len(rows)} listings -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
