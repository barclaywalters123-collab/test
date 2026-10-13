# eBay Reseller Research Agent

An AI agent that finds proven product themes to make your own version of and sell on eBay, TikTok Shop and Amazon. It checks what has actually **sold** on eBay recently, compares that with how many competing listings are active, works out the most you can pay a bulk supplier per unit and still make your margin, flags designs that belong to a specific shop, and gives you a ranked list. It's built on the Claude API with a hand-written agent loop, so you can see exactly how it works.

```
python agent.py --research
  -> research_market(query="personalized family name doormat")
  -> research_market(query="halloween coffee mug")      (several ideas in parallel)
  -> search_ebay(query="halloween mug")                  (how crowded is it?)
agent: "Top 10 ideas, ranked: ..."
```

## Setup

```bash
cd ebay-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then put your keys in .env
```

- **Claude API key** (required): https://platform.claude.com/settings/keys
- **eBay keys** (optional at first): without them the agent runs in **mock mode** with fake numbers, so you can try it right away. To get real data, create a free developer account at https://developer.ebay.com, create an app, and copy the **Production** App ID (Client ID) and Cert ID (Client Secret) into `.env`.

### Getting sold-listing data (important)

eBay's standard search API only shows **active** listings. **Sold** listings come from eBay's **Marketplace Insights API**, which you have to request access to: in the eBay developer portal, apply for it under your app's application access / API access settings.

Until you're approved, the agent still runs. It reports active-listing counts and sourcing prices, and marks sold prices, sold counts and sell-through as **"not verified"** instead of guessing. While you wait, you can check sold numbers by hand: search eBay, then tick **Sold items** in the filters.

## Run it

```bash
python agent.py --research                          # run the research brief in prompts.py, then ask follow-ups
python agent.py "seasonal garden flags to resell"   # a one-off question
python agent.py                                     # chat mode
```

A full research run makes a few dozen tool calls and takes a few minutes. Expect it to cost a few dollars in Claude API usage per run (rough estimate; it depends on how many ideas it checks).

Tool calls are printed as they happen (`-> search_ebay(...)`), so you can watch the agent work.

## How it's put together

| File | What it does | When you'd edit it |
|---|---|---|
| `prompts.py` | `SYSTEM_PROMPT` (how the agent researches and its rules) and `RESEARCH_BRIEF` (your research request) | **Most often.** Change the niche or output format here |
| `config.py` | Money settings: eBay fees, your target margin, your per-unit budget | When your numbers change |
| `tools.py` | The tools Claude can call (`research_market`, `search_ebay`, `get_item_details`) and the code that runs them | To add or change tools |
| `ebay_client.py` | Talks to eBay (Browse API for active listings, Marketplace Insights for sold) and holds the mock data | To use more eBay fields or filters |
| `agent.py` | The agent loop: calls Claude, runs tools, sends results back, repeats | Rarely: model, effort level, turn limit |

### The loop (`agent.py` → `run_agent`)

1. Send the conversation, the system prompt and the tool list to Claude.
2. If Claude's reply contains `tool_use` blocks, run each tool and send the results back as `tool_result` blocks.
3. Repeat until Claude answers without calling a tool, or until `MAX_TURNS` is reached.

Tool errors are sent back with `is_error: True` instead of crashing, so Claude can fix a bad item ID or retry a search.

### The `research_market` tool

This is the main tool. In one call per idea it returns:
- **Sold**: number of sold listings in the last 30–90 days, plus the median, low and high sold price
- **Active**: how many listings are currently up
- **Sell-through**: sold ÷ active (above 100% is strong demand, under 30% is a crowded market)
- **Competitor prices**: the cheapest active listings, including shipping
- **Max unit cost**: the most you can pay your supplier per unit and still hit your target margin after eBay fees (settings in `config.py`)

Doing the math in code instead of having Claude read hundreds of raw listings keeps the agent cheaper and its numbers consistent.

## Notes and limits

- **Make your own designs.** Common themes, phrases and layouts (a family name doormat, "Mama Bear", pumpkins) are fair game. Another seller's actual artwork, photos and listing text are not: copying them is copyright infringement, and eBay, Amazon and TikTok Shop take down listings and suspend accounts over it. The agent labels each idea as a generic theme or a specific shop's design.
- **eBay data only.** The agent has no TikTok Shop or Amazon data. Anything it says about those channels is general guidance, not numbers. Check fees and category rules on each platform before listing, especially Amazon.
- **Money math is an estimate.** It uses about 13.6% + $0.40 per order for eBay fees and assumes the buyer pays shipping. Amazon and TikTok Shop fees are different. Supplier prices aren't something the agent can see; get real quotes.
- The agent skips licensed or branded items (sports teams, characters, brand logos), but it judges from titles and descriptions. Double-check anything before you order inventory.
