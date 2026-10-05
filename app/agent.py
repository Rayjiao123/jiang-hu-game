"""A small streaming tool-use loop for DeepSeek's OpenAI-compatible chat API.

The model only *asks* for things through tools. Every tool is a Python function
on the server, so game rules (trust, secrets, what gets saved) are enforced in
code, never by the prompt.
"""
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from . import config, ratelimit


class ToolError(Exception):
    """Raised by a tool to send an error message back to the model (the turn continues)."""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    run: Callable[[dict], Any]

    def schema(self) -> dict:
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass
class Turn:
    """Collects UI events that tools emit while they run."""
    events: list = field(default_factory=list)

    def emit(self, **event) -> None:
        self.events.append(event)


def run(client, model: str, messages: list[dict], tools: list[Tool], turn: Turn, visitor_id: str,
        max_rounds: int = 5, max_tokens: int = 700) -> Iterator[dict]:
    """Yields events: {"type": "text", "delta"}, any events tools emit, and finally
    {"type": "done", "text"} with the whole reply. `messages` is extended in place."""
    by_name = {t.name: t for t in tools}
    schemas = [t.schema() for t in tools]
    said_anything = False
    full_text: list[str] = []

    for round_no in range(max_rounds):
        ratelimit.check(visitor_id)
        last = round_no == max_rounds - 1
        kwargs: dict = dict(model=model, messages=messages, stream=True, max_tokens=max_tokens,
                            extra_body={"thinking": {"type": "disabled"}})
        if schemas:
            kwargs.update(tools=schemas, tool_choice="none" if last else "auto")
        stream = client.chat.completions.create(**kwargs)

        content: list[str] = []
        calls: dict[int, dict] = {}
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                if not content and said_anything:
                    full_text.append("\n\n")
                    yield {"type": "text", "delta": "\n\n"}
                content.append(delta.content)
                full_text.append(delta.content)
                said_anything = True
                yield {"type": "text", "delta": delta.content}
            for tc in delta.tool_calls or []:
                slot = calls.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] += tc.function.name
                if tc.function and tc.function.arguments:
                    slot["args"] += tc.function.arguments

        if not calls:
            yield {"type": "done", "text": "".join(full_text).strip()}
            return

        ordered = [calls[i] for i in sorted(calls)]
        messages.append({
            "role": "assistant",
            "content": "".join(content) or None,
            "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["args"] or "{}"}} for c in ordered],
        })
        for c in ordered:
            result = _call(by_name.get(c["name"]), c["args"])
            yield from turn.events
            turn.events.clear()
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result, ensure_ascii=False)})

    yield {"type": "done", "text": "".join(full_text).strip()}


def _call(tool: Tool | None, raw_args: str) -> Any:
    if tool is None:
        return {"error": "Unknown tool."}
    try:
        args = json.loads(raw_args or "{}")
        if not isinstance(args, dict):
            raise ValueError
    except ValueError:
        return {"error": "Arguments were not a JSON object. Try again."}
    try:
        return tool.run(args)
    except ToolError as e:
        return {"error": str(e)}


def history(turns: list[dict]) -> list[dict]:
    """Only plain user/assistant text is kept between requests; tool effects live in game state."""
    return [{"role": t["role"], "content": t["content"]} for t in turns[-config.MAX_HISTORY_TURNS:]]
