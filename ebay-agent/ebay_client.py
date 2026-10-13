"""Small wrapper around the eBay Browse API.

If EBAY_CLIENT_ID / EBAY_CLIENT_SECRET aren't set, it runs in MOCK mode and
returns fake listings, so you can build and test the agent before you have
eBay keys.

eBay docs: https://developer.ebay.com/api-docs/buy/browse/overview.html
"""

import os
import time

import requests

API_HOSTS = {
    "production": "https://api.ebay.com",
    "sandbox": "https://api.sandbox.ebay.com",
}

# Friendly sort names the agent can use -> eBay's sort values.
# "best_match" means "don't send a sort" (eBay's default ranking).
SORTS = {
    "best_match": None,
    "price_low": "price",
    "price_high": "-price",
    "newest": "newlyListed",
    "ending_soon": "endingSoonest",
}

CONDITIONS = {"new": "NEW", "used": "USED"}


class EbayClient:
    def __init__(self):
        self.client_id = os.environ.get("EBAY_CLIENT_ID", "")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET", "")
        self.host = API_HOSTS[os.environ.get("EBAY_ENV", "production")]
        self.marketplace = os.environ.get("EBAY_MARKETPLACE", "EBAY_US")
        self.mock = not (self.client_id and self.client_secret)
        self._token = None
        self._token_expires = 0.0

    # --- auth -------------------------------------------------------------

    def _get_token(self):
        """Get an application access token (client credentials flow), cached until it expires."""
        if self._token and time.time() < self._token_expires - 60:
            return self._token
        resp = requests.post(
            f"{self.host}/identity/v1/oauth2/token",
            auth=(self.client_id, self.client_secret),
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=20,
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._token_expires = time.time() + body.get("expires_in", 7200)
        return self._token

    def _get(self, path, params=None):
        resp = requests.get(
            f"{self.host}{path}",
            params=params,
            headers={
                "Authorization": f"Bearer {self._get_token()}",
                "X-EBAY-C-MARKETPLACE-ID": self.marketplace,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    # --- public methods (these back the agent's tools) --------------------

    def search(self, query, min_price=None, max_price=None, condition=None,
               sort="best_match", limit=10):
        if self.mock:
            return _mock_search(query, min_price, max_price, condition, sort, limit)

        filters = []
        if min_price is not None or max_price is not None:
            lo = "" if min_price is None else min_price
            hi = "" if max_price is None else max_price
            currency = "GBP" if self.marketplace == "EBAY_GB" else "USD"
            filters.append(f"price:[{lo}..{hi}],priceCurrency:{currency}")
        if condition in CONDITIONS:
            filters.append(f"conditions:{{{CONDITIONS[condition]}}}")

        params = {"q": query, "limit": max(1, min(int(limit), 50))}
        if filters:
            params["filter"] = ",".join(filters)
        if SORTS.get(sort):
            params["sort"] = SORTS[sort]

        data = self._get("/buy/browse/v1/item_summary/search", params)
        return {
            "total_matches": data.get("total", 0),
            "items": [_summarize(item) for item in data.get("itemSummaries", [])],
        }

    def get_item(self, item_id):
        if self.mock:
            return _mock_item(item_id)
        item = self._get(f"/buy/browse/v1/item/{item_id}")
        summary = _summarize(item)
        summary.update({
            "description": (item.get("shortDescription") or "")[:1000],
            "brand": item.get("brand"),
            "item_location": (item.get("itemLocation") or {}).get("country"),
            "returns_accepted": (item.get("returnTerms") or {}).get("returnsAccepted"),
            "quantity_sold": (item.get("estimatedAvailabilities") or [{}])[0].get("estimatedSoldQuantity"),
        })
        return summary


def _summarize(item):
    """Keep only the fields the agent needs. Smaller tool results = cheaper, more focused agent."""
    price = item.get("price") or {}
    seller = item.get("seller") or {}
    shipping = (item.get("shippingOptions") or [{}])[0].get("shippingCost") or {}
    return {
        "item_id": item.get("itemId"),
        "title": item.get("title"),
        "price": f"{price.get('value')} {price.get('currency')}" if price else None,
        "shipping": f"{shipping.get('value')} {shipping.get('currency')}" if shipping else "unknown",
        "condition": item.get("condition"),
        "seller": seller.get("username"),
        "seller_feedback_pct": seller.get("feedbackPercentage"),
        "seller_feedback_score": seller.get("feedbackScore"),
        "buying_options": item.get("buyingOptions"),
        "url": item.get("itemWebUrl"),
    }


# --- mock data --------------------------------------------------------------

_MOCK_ITEMS = [
    {"item_id": "v1|1001|0", "title": "{q} - Brand New, Sealed", "price": 129.99,
     "condition": "New", "seller": "top_rated_store", "fb": "99.8", "score": 15230, "ship": 0.0},
    {"item_id": "v1|1002|0", "title": "{q} - Lightly Used, Works Great", "price": 74.50,
     "condition": "Used", "seller": "casual_seller_42", "fb": "100.0", "score": 87, "ship": 8.99},
    {"item_id": "v1|1003|0", "title": "{q} - For Parts / Not Working", "price": 19.00,
     "condition": "For parts or not working", "seller": "parts_bin", "fb": "97.1", "score": 2210, "ship": 12.00},
    {"item_id": "v1|1004|0", "title": "{q} - Open Box, Like New", "price": 99.00,
     "condition": "Open box", "seller": "deal_hunter_outlet", "fb": "99.1", "score": 4410, "ship": 5.00},
    {"item_id": "v1|1005|0", "title": "{q} - Refurbished w/ 1yr Warranty", "price": 89.95,
     "condition": "Certified - Refurbished", "seller": "refurb_pros", "fb": "98.7", "score": 9921, "ship": 0.0},
]


def _mock_format(m, query):
    return {
        "item_id": m["item_id"],
        "title": m["title"].format(q=query.title()),
        "price": f"{m['price']:.2f} USD",
        "shipping": f"{m['ship']:.2f} USD",
        "condition": m["condition"],
        "seller": m["seller"],
        "seller_feedback_pct": m["fb"],
        "seller_feedback_score": m["score"],
        "buying_options": ["FIXED_PRICE"],
        "url": f"https://www.ebay.com/itm/{m['item_id'].split('|')[1]}",
    }


def _mock_search(query, min_price, max_price, condition, sort, limit):
    items = list(_MOCK_ITEMS)
    if min_price is not None:
        items = [m for m in items if m["price"] >= min_price]
    if max_price is not None:
        items = [m for m in items if m["price"] <= max_price]
    if condition == "new":
        items = [m for m in items if m["condition"] == "New"]
    elif condition == "used":
        items = [m for m in items if m["condition"] != "New"]
    if sort == "price_low":
        items.sort(key=lambda m: m["price"])
    elif sort == "price_high":
        items.sort(key=lambda m: -m["price"])
    items = items[: max(1, min(int(limit), 50))]
    return {"total_matches": len(items), "mock_data": True,
            "items": [_mock_format(m, query) for m in items]}


def _mock_item(item_id):
    for m in _MOCK_ITEMS:
        if m["item_id"] == item_id:
            details = _mock_format(m, "sample item")
            details.update({"description": "Mock listing description.", "brand": "MockBrand",
                            "item_location": "US", "returns_accepted": True, "mock_data": True})
            return details
    raise ValueError(f"No item with id {item_id!r}")
