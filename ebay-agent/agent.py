"""eBay product-finder agent.

Usage:
    python agent.py --research                                 # run the research brief in prompts.py
    python agent.py "seasonal doormats under $25 to resell"    # one question
    python agent.py                                            # chat mode

The agent loop:
    send the conversation to Claude
      -> Claude replies with text and/or tool calls
      -> we run the tools and send the results back
      -> repeat until Claude stops calling tools
"""

import os
import sys
from pathlib import Path

import anthropic


def load_dotenv(path=Path(__file__).parent / ".env"):
    """Tiny .env loader so you don't need an extra package. Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_dotenv()

from prompts import RESEARCH_BRIEF, SYSTEM_PROMPT  # noqa: E402  (import after .env is loaded)
from tools import TOOLS, ebay, run_tool  # noqa: E402

MODEL = "claude-opus-5-5"
MAX_TURNS = 40  # safety cap: max Claude calls per question, so a confused agent can't loop forever

client = anthropic.Anthropic()


def run_agent(messages):
    """Run the agent loop on `messages` (modified in place). Returns Claude's final text."""
    for _ in range(MAX_TURNS):
        # Streaming lets a long final report finish without hitting HTTP timeouts.
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=64000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
            output_config={"effort": "high"},  # research benefits from thoroughness; "medium"/"low" are cheaper
            # If a safety classifier declines the request, retry on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            response = stream.get_final_message()

        if response.stop_reason == "refusal":
            return "Sorry, Claude declined this request."

        # Keep the full content (thinking, text, tool calls), not just the text.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            text = "".join(b.text for b in response.content if b.type == "text")
            if response.stop_reason == "max_tokens":
                text += "\n\n[Cut off: the response hit max_tokens.]"
            return text

        # Run every tool Claude asked for; send all results back in a single message.
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print(f"  -> {block.name}({block.input})", file=sys.stderr)
            output, is_error = run_tool(block.name, block.input)
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
                "is_error": is_error,
            })
        messages.append({"role": "user", "content": results})

    return f"Stopped after {MAX_TURNS} turns without a final answer."


def main():
    if ebay.mock:
        print("[MOCK MODE] No eBay keys set, so listings are fake. See README.md.\n", file=sys.stderr)

    messages = []

    args = sys.argv[1:]
    first = RESEARCH_BRIEF if args == ["--research"] else " ".join(args)
    if first:
        messages.append({"role": "user", "content": first})
        print(run_agent(messages))
        if args != ["--research"]:
            return
        print("\nAsk follow-up questions, or Ctrl+C to quit.")
    else:
        print("What should I research on eBay? (Ctrl+C to quit)")

    while True:
        try:
            question = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        messages.append({"role": "user", "content": question})
        print("\nagent> " + run_agent(messages))


if __name__ == "__main__":
    main()
