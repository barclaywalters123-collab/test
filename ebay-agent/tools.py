"""The agent's tools: what Claude sees (TOOLS) and the code that runs them (run_tool).

To add a tool:
  1. Add its schema to TOOLS (name, description, input_schema).
  2. Add a branch for it in run_tool().
Claude decides when to call a tool purely from its name, description, and
parameter descriptions, so write them carefully.
"""

import json

from ebay_client import EbayClient, SORTS

ebay = EbayClient()

TOOLS = [
    {
        "name": "search_ebay",
        "description": (
            "Search eBay listings. Returns up to `limit` listings with item_id, title, price, "
            "shipping cost, condition, seller feedback, and URL. Run several searches with "
            "different wording when the first one doesn't turn up good matches."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords, e.g. 'Sony WH-1000XM5 headphones'."},
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
            "Get full details for one listing by its item_id (from search_ebay): description, "
            "brand, location, return policy. Use this to check promising listings before recommending them."
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


def run_tool(name, args):
    """Run a tool and return (result_text, is_error)."""
    try:
        if name == "search_ebay":
            result = ebay.search(**args)
        elif name == "get_item_details":
            result = ebay.get_item(args["item_id"])
        else:
            return f"Unknown tool: {name}", True
        return json.dumps(result), False
    except Exception as e:  # send the error back so Claude can adjust and retry
        return f"{type(e).__name__}: {e}", True
