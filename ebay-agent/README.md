# eBay Product Finder Agent

A starter AI agent that searches eBay and recommends the best listings for what you ask for. It's built on the Claude API with a hand-written agent loop, so you can see exactly how it works.

```
you: "Sony noise-cancelling headphones under $200, used is fine"
  -> search_ebay(query="Sony WH-1000XM5", max_price=200)
  -> search_ebay(query="Sony WH-1000XM4", max_price=200)
  -> get_item_details(item_id="v1|...")
agent: "Here are the 3 best options..."
```

## Setup

```bash
cd ebay-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then put your keys in .env
```

- **Claude API key** (required): https://platform.claude.com/settings/keys
- **eBay keys** (optional at first): without them the agent runs in **mock mode** with fake listings, so you can try it right away. To get real listings, create a free developer account at https://developer.ebay.com, create an app, and copy the **Production** App ID (Client ID) and Cert ID (Client Secret) into `.env`.

## Run it

```bash
python agent.py "a used Nintendo Switch OLED under $250"   # one question
python agent.py                                           # chat mode with follow-ups
```

Tool calls are printed as they happen (`-> search_ebay(...)`), so you can watch the agent work.

## How it's put together

| File | What it does | When you'd edit it |
|---|---|---|
| `prompts.py` | The system prompt: how the agent should search, judge and present listings | **Most often.** This is where your instructions go |
| `tools.py` | The tools Claude can call (`search_ebay`, `get_item_details`) and the code that runs them | To add or change tools |
| `ebay_client.py` | Talks to the eBay Browse API (login, search, item details) and holds the mock data | To use more eBay fields or filters |
| `agent.py` | The agent loop: calls Claude, runs tools, sends results back, repeats | Rarely: model, effort level, turn limit |

### The loop (`agent.py` → `run_agent`)

1. Send the conversation, the system prompt and the tool list to Claude.
2. If Claude's reply contains `tool_use` blocks, run each tool and send the results back as `tool_result` blocks.
3. Repeat until Claude answers without calling a tool, or until `MAX_TURNS` is reached.

Tool errors are sent back with `is_error: True` instead of crashing, so Claude can fix a bad item ID or retry a search.

## Ideas for next steps

- Add a `filter_by_seller_rating` setting or a `compare_items` tool.
- Save favorite searches and run them every morning to catch new deals.
- Add a price-history check so the agent knows what counts as a good deal.
