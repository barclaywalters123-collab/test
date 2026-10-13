# eBay Reseller Research Agent

An AI agent that finds products worth reselling on eBay. It checks what has actually **sold** recently, compares that with how many competing listings are active, estimates what you'd pay to source each item, and gives you a ranked list. It's built on the Claude API with a hand-written agent loop, so you can see exactly how it works.

```
python agent.py --research
  -> research_market(query="personalized family name doormat")
  -> research_market(query="halloween coffee mug")      (several ideas in parallel)
  -> search_ebay(query="halloween mug lot", sort="price_low")
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

A full research run makes a few dozen tool calls and takes a few minutes. Expect it to cost roughly a dollar or two in Claude API usage; it varies.

Tool calls are printed as they happen (`-> search_ebay(...)`), so you can watch the agent work.

## How it's put together

| File | What it does | When you'd edit it |
|---|---|---|
| `prompts.py` | `SYSTEM_PROMPT` (how the agent researches, its rules, the fee estimate) and `RESEARCH_BRIEF` (your research request) | **Most often.** Change the niche, budget or output format here |
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
- **Sourcing estimate**: the cheapest active listings including shipping

Doing the math in code instead of having Claude read hundreds of raw listings keeps the agent cheaper and its numbers consistent.

## Notes and limits

- Profit estimates use about 13.6% + $0.40 per order for eBay fees (`FEE_RATE` in `prompts.py`). Check eBay's fee page for your category.
- Sourcing on eBay to resell on eBay leaves thin margins. Lots and bulk listings ("halloween mug lot") are usually where the margin is, and the agent is told to look for them.
- The agent skips licensed or branded items (sports teams, characters, brand logos), but it judges from titles and descriptions. Double-check anything before you buy inventory.
