"""The agent's tools: what Claude sees (TOOLS) and the code that runs them (run_tool).

To add a tool:
  1. Add its schema to TOOLS (name, description, input_schema).
  2. Add a branch for it in run_tool().
Claude decides when to call a tool purely from its name, description, and
parameter descriptions, so write them carefully.
"""

import json
import statistics

from ebay_client import EbayClient, SORTS, SoldDataUnavailable

ebay = EbayClient()

TOOLS = [
    {
        "name": "research_market",
        "description": (
            "Demand check for one product idea. Returns, for the search terms: SOLD listings over the last "
            "`days` days (count, median/low/high sold price, examples), the number of ACTIVE listings, "
            "sell-through (sold listings / active listings), and the cheapest active listings with shipping "
            "(a rough sourcing-cost estimate). If sold data can't be fetched, `sold.available` is false and "
            "`sold.reason` explains why. Report that as unverified; don't estimate it. "
            "Call this once per idea; run several ideas in parallel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "eBay search terms, e.g. 'personalized family name doormat'."},
                "days": {"type": "integer", "minimum": 1, "maximum": 90, "description": "Sold-history window in days (eBay keeps up to 90). Defaults to 90."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_ebay",
        "description": (
            "Search ACTIVE eBay listings. Returns up to `limit` listings with item_id, title, price, "
            "shipping cost, condition, seller feedback, and URL, plus total_matches (how many active "
            "listings exist). Use it to check sourcing options (e.g. add 'lot' or 'wholesale' to the query, "
            "sort by price_low) or to look at the competition."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords, e.g. 'halloween coffee mug lot'."},
                "min_price": {"type": "number", "description": "Minimum item price (optional)."},
                "max_price": {"type": "number", "description": "Maximum item price, not counting shipping (optional)."},
                "condition": {"type": "string", "enum": ["new", "used"], "description": "Only new or only used items (optional)."},
                "sort": {"type": "string", "enum": list(SORTS), "description": "Sort order. Defaults to best_match."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "description": "How many results to return. Defaults to 10."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_item_details",
        "description": (
            "Get full details for one active listing by its item_id (from search_ebay): description, "
            "brand, location, return policy. Use it to check whether a listing is licensed/branded."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "The item_id from a search_ebay result, e.g. 'v1|1234567890|0'."},
            },
            "required": ["item_id"],
        },
    },
]


def _parse_amount(text):
    """'12.99 USD' -> 12.99; anything unparseable -> None."""
    try:
        return float(str(text).split()[0])
    except (ValueError, IndexError):
        return None


def research_market(query, days=90):
    result = {"query": query}

    try:
        result["sold"] = {"available": True, **ebay.sold_stats(query, days)}
    except SoldDataUnavailable as e:
        result["sold"] = {"available": False, "reason": str(e)}

    active = ebay.search(query, sort="price_low", limit=20)
    landed = []  # price + shipping, where both are known
    for item in active["items"]:
        price, ship = _parse_amount(item["price"]), _parse_amount(item["shipping"])
        if price is not None:
            landed.append(round(price + (ship or 0), 2))
    result["active"] = {
        "active_listings": active["total_matches"],
        "cheapest_landed_costs": landed[:5],
        "median_landed_cost_of_cheapest_20": round(statistics.median(landed), 2) if landed else None,
        "cheapest_examples": [
            {k: item[k] for k in ("title", "price", "shipping", "condition", "url")}
            for item in active["items"][:3]
        ],
    }
    if active.get("mock_data"):
        result["active"]["mock_data"] = True

    sold_count = result["sold"].get("sold_listings")
    if result["sold"]["available"] and active["total_matches"]:
        result["sell_through_pct"] = round(100 * sold_count / active["total_matches"], 1)
    else:
        result["sell_through_pct"] = None
    return result


def run_tool(name, args):
    """Run a tool and return (result_text, is_error)."""
    try:
        if name == "research_market":
            result = research_market(**args)
        elif name == "search_ebay":
            result = ebay.search(**args)
        elif name == "get_item_details":
            result = ebay.get_item(args["item_id"])
        else:
            return f"Unknown tool: {name}", True
        return json.dumps(result), False
    except Exception as e:  # send the error back so Claude can adjust and retry
        return f"{type(e).__name__}: {e}", True
