"""
Quick wow tools for Universal Soul — no heavy deps.

Works out of the box (DuckDuckGo / Wikipedia / wttr.in / etc.).
Optional Google Custom Search when GOOGLE_CSE_ID + GOOGLE_API_KEY are set.
"""

from __future__ import annotations

import ast
import json
import math
import operator
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from core.integrations import google_oauth

USER_AGENT = "UniversalSoulAI/1.0 (+local companion; +https://github.com/Awehbelekker/Universal-AI-Soul-Unlimited)"
TIMEOUT = 18


def _http_json(url: str, headers: Optional[Dict[str, str]] = None) -> Any:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_text(url: str, headers: Optional[Dict[str, str]] = None) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _ok(tool: str, summary: str, **extra: Any) -> Dict[str, Any]:
    return {"ok": True, "tool": tool, "summary": summary, **extra}


def _err(tool: str, error: str) -> Dict[str, Any]:
    return {"ok": False, "tool": tool, "error": error, "summary": f"Error: {error}"}


# --- individual tools -------------------------------------------------------


def tool_web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Web search — Google CSE if configured, else DuckDuckGo."""
    q = (query or "").strip()
    if not q:
        return _err("web_search", "query required")
    max_results = max(1, min(int(max_results or 5), 8))

    google_oauth.load_dotenv()
    cse_id = (os.environ.get("GOOGLE_CSE_ID") or "").strip()
    api_key = (os.environ.get("GOOGLE_API_KEY") or "").strip()
    google_fail = None
    if cse_id and api_key:
        try:
            url = (
                "https://www.googleapis.com/customsearch/v1?"
                + urllib.parse.urlencode(
                    {"key": api_key, "cx": cse_id, "q": q, "num": max_results}
                )
            )
            data = _http_json(url)
            items = []
            for it in data.get("items") or []:
                items.append(
                    {
                        "title": it.get("title"),
                        "url": it.get("link"),
                        "snippet": it.get("snippet"),
                    }
                )
            if items:
                lines = [f"- {i['title']}: {i['snippet']} ({i['url']})" for i in items]
                return _ok(
                    "web_search",
                    f"Google results for “{q}”:\n" + "\n".join(lines),
                    provider="google_cse",
                    results=items,
                )
            google_fail = "empty CSE results"
        except Exception as exc:
            google_fail = str(exc)

    items: List[Dict[str, Any]] = []
    errors: List[str] = []
    if google_fail:
        errors.append(f"Google CSE: {google_fail}")

    # Instant Answer API (may be empty / blocked)
    try:
        ia_url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": q, "format": "json", "no_html": 1, "skip_disambig": 1}
        )
        raw = _http_text(ia_url)
        if raw.strip().startswith(("{", "[")):
            ia = json.loads(raw)
            abstract = (ia.get("AbstractText") or "").strip()
            if abstract:
                items.append(
                    {
                        "title": ia.get("Heading") or q,
                        "url": ia.get("AbstractURL") or "",
                        "snippet": abstract,
                    }
                )
            for topic in (ia.get("RelatedTopics") or [])[: max_results + 2]:
                if not isinstance(topic, dict) or "Topics" in topic:
                    continue
                text = (topic.get("Text") or "").strip()
                url = (topic.get("FirstURL") or "").strip()
                if text:
                    items.append(
                        {
                            "title": text.split(" - ")[0][:80],
                            "url": url,
                            "snippet": text,
                        }
                    )
                if len(items) >= max_results:
                    break
    except Exception as exc:
        errors.append(f"DDG IA: {exc}")

    # Wikipedia opensearch as a solid always-on fallback for "search"
    if len(items) < 2:
        try:
            wiki = tool_wikipedia(q)
            if wiki.get("ok"):
                items.append(
                    {
                        "title": wiki.get("title") or q,
                        "url": wiki.get("url") or "",
                        "snippet": (wiki.get("extract") or "")[:280],
                    }
                )
        except Exception as exc:
            errors.append(f"wiki: {exc}")

    # HTML lite scrape
    if len(items) < max_results:
        try:
            html_url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode(
                {"q": q}
            )
            html = _http_text(html_url)
            for m in re.finditer(
                r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                html,
                flags=re.I | re.S,
            ):
                href = urllib.parse.unquote(m.group(1))
                if "uddg=" in href:
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                    href = (qs.get("uddg") or [href])[0]
                title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
                if title and href.startswith("http"):
                    items.append({"title": title, "url": href, "snippet": title})
                if len(items) >= max_results:
                    break
        except Exception as exc:
            errors.append(f"DDG HTML: {exc}")

    # Brave-less last resort: Bing news-ish via Wikipedia already tried;
    # try Wikidata search API
    if not items:
        try:
            wd = (
                "https://www.wikidata.org/w/api.php?"
                + urllib.parse.urlencode(
                    {
                        "action": "wbsearchentities",
                        "search": q,
                        "language": "en",
                        "format": "json",
                        "limit": max_results,
                    }
                )
            )
            data = _http_json(wd)
            for row in data.get("search") or []:
                items.append(
                    {
                        "title": row.get("label") or q,
                        "url": row.get("concepturi") or "",
                        "snippet": row.get("description") or "",
                    }
                )
        except Exception as exc:
            errors.append(f"wikidata: {exc}")

    if not items:
        detail = "; ".join(errors) if errors else "no hits"
        return _err("web_search", f"No results for “{q}” ({detail})")

    lines = [
        f"- {i['title']}: {i.get('snippet') or ''} ({i.get('url') or ''})".strip()
        for i in items[:max_results]
    ]
    note = ""
    if google_fail:
        note = "\n(Google CSE unavailable; used open web fallbacks)"
    return _ok(
        "web_search",
        f"Search results for “{q}”:{note}\n" + "\n".join(lines),
        provider="duckduckgo" if not google_fail else "fallback",
        results=items[:max_results],
    )


def tool_wikipedia(query: str) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return _err("wikipedia", "query required")
    try:
        search_url = (
            "https://en.wikipedia.org/w/api.php?"
            + urllib.parse.urlencode(
                {
                    "action": "opensearch",
                    "search": q,
                    "limit": 1,
                    "namespace": 0,
                    "format": "json",
                }
            )
        )
        data = _http_json(search_url)
        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        if not titles:
            return _err("wikipedia", f"No Wikipedia page for “{q}”")
        title = titles[0]
        sum_url = (
            "https://en.wikipedia.org/api/rest_v1/page/summary/"
            + urllib.parse.quote(title.replace(" ", "_"))
        )
        page = _http_json(sum_url)
        extract = (page.get("extract") or "").strip()
        url = (page.get("content_urls") or {}).get("desktop", {}).get("page") or page.get(
            "url"
        )
        return _ok(
            "wikipedia",
            f"{page.get('title') or title}: {extract}\nSource: {url}",
            title=page.get("title") or title,
            url=url,
            extract=extract,
        )
    except Exception as exc:
        return _err("wikipedia", str(exc))


def tool_weather(place: str) -> Dict[str, Any]:
    place = (place or "").strip() or "Cape Town"
    try:
        path = urllib.parse.quote(place)
        url = f"https://wttr.in/{path}?format=j1"
        data = _http_json(url)
        cur = (data.get("current_condition") or [{}])[0]
        nearest = (data.get("nearest_area") or [{}])[0]
        area = ""
        if nearest:
            area_parts = [
                (nearest.get("areaName") or [{}])[0].get("value"),
                (nearest.get("country") or [{}])[0].get("value"),
            ]
            area = ", ".join(p for p in area_parts if p)
        desc = ((cur.get("weatherDesc") or [{}])[0].get("value")) or ""
        temp_c = cur.get("temp_C")
        feels = cur.get("FeelsLikeC")
        humidity = cur.get("humidity")
        wind = cur.get("windspeedKmph")
        summary = (
            f"Weather in {area or place}: {desc}, {temp_c}°C "
            f"(feels {feels}°C), humidity {humidity}%, wind {wind} km/h."
        )
        return _ok(
            "weather",
            summary,
            place=area or place,
            temp_c=temp_c,
            description=desc,
        )
    except Exception as exc:
        return _err("weather", str(exc))


def tool_define(word: str) -> Dict[str, Any]:
    word = (word or "").strip()
    if not word:
        return _err("define", "word required")
    try:
        url = "https://api.dictionaryapi.dev/api/v2/entries/en/" + urllib.parse.quote(
            word
        )
        data = _http_json(url)
        if not isinstance(data, list) or not data:
            return _err("define", f"No definition for “{word}”")
        entry = data[0]
        meanings = []
        for m in (entry.get("meanings") or [])[:3]:
            pos = m.get("partOfSpeech") or ""
            defs = []
            for d in (m.get("definitions") or [])[:2]:
                defs.append(d.get("definition") or "")
            meanings.append(f"{pos}: " + "; ".join(defs))
        phonetic = entry.get("phonetic") or ""
        summary = f"{entry.get('word')} {phonetic}\n" + "\n".join(meanings)
        return _ok("define", summary, word=entry.get("word"), meanings=meanings)
    except urllib.error.HTTPError:
        return _err("define", f"No definition for “{word}”")
    except Exception as exc:
        return _err("define", str(exc))


_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_SAFE_FUNCS = {
    "sqrt": math.sqrt,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "pi": math.pi,
    "e": math.e,
}


def _eval_node(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Num):  # py<3.8 compat
        return node.n
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        fn = _SAFE_FUNCS.get(node.func.id)
        if not fn or not callable(fn):
            raise ValueError("function not allowed")
        args = [_eval_node(a) for a in node.args]
        return fn(*args)
    if isinstance(node, ast.Name) and node.id in ("pi", "e"):
        return _SAFE_FUNCS[node.id]
    raise ValueError("unsafe expression")


def tool_calc(expression: str) -> Dict[str, Any]:
    expr = (expression or "").strip()
    if not expr:
        return _err("calc", "expression required")
    try:
        tree = ast.parse(expr, mode="eval")
        value = _eval_node(tree)
        return _ok("calc", f"{expr} = {value}", expression=expr, value=value)
    except Exception as exc:
        return _err("calc", f"Could not evaluate: {exc}")


def tool_time_now(tz: str = "") -> Dict[str, Any]:
    tz = (tz or "").strip()
    try:
        if tz:
            now = datetime.now(ZoneInfo(tz))
            label = tz
        else:
            now = datetime.now().astimezone()
            label = str(now.tzinfo) or "local"
        iso = now.isoformat(timespec="seconds")
        human = now.strftime("%A, %d %B %Y · %H:%M:%S")
        return _ok(
            "time_now",
            f"Current time ({label}): {human} ({iso})",
            timezone=label,
            iso=iso,
            human=human,
        )
    except Exception as exc:
        # fallback UTC
        now = datetime.now(timezone.utc)
        return _ok(
            "time_now",
            f"Current time (UTC): {now.isoformat(timespec='seconds')} "
            f"(requested tz failed: {exc})",
            timezone="UTC",
            iso=now.isoformat(timespec="seconds"),
        )


def tool_translate(text: str, to: str = "en", fr: str = "auto") -> Dict[str, Any]:
    text = (text or "").strip()
    to = (to or "en").strip() or "en"
    fr = (fr or "auto").strip() or "auto"
    if not text:
        return _err("translate", "text required")
    try:
        url = "https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(
            {"q": text[:450], "langpair": f"{fr}|{to}"}
        )
        data = _http_json(url)
        translated = ((data.get("responseData") or {}).get("translatedText") or "").strip()
        if not translated:
            return _err("translate", "empty translation")
        return _ok(
            "translate",
            f"[{fr}→{to}] {translated}",
            source_text=text,
            translated=translated,
            from_lang=fr,
            to_lang=to,
        )
    except Exception as exc:
        return _err("translate", str(exc))


def tool_news(topic: str = "world") -> Dict[str, Any]:
    topic = (topic or "world").strip() or "world"
    # Reuse search focused on recent news
    return tool_web_search(f"{topic} news", max_results=5)


def tool_crypto(symbol: str = "bitcoin") -> Dict[str, Any]:
    symbol = (symbol or "bitcoin").strip().lower()
    # map common tickers
    aliases = {
        "btc": "bitcoin",
        "eth": "ethereum",
        "sol": "solana",
        "xrp": "ripple",
        "doge": "dogecoin",
    }
    coin = aliases.get(symbol, symbol)
    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price?"
            + urllib.parse.urlencode(
                {
                    "ids": coin,
                    "vs_currencies": "usd,eur,zar",
                    "include_24hr_change": "true",
                }
            )
        )
        data = _http_json(url)
        row = data.get(coin)
        if not row:
            return _err("crypto", f"Unknown coin “{symbol}” — try bitcoin, ethereum, solana")
        ch = row.get("usd_24h_change")
        ch_s = f"{ch:+.2f}%" if isinstance(ch, (int, float)) else "?"
        summary = (
            f"{coin}: ${row.get('usd')} USD · €{row.get('eur')} · "
            f"R{row.get('zar')} (24h {ch_s})"
        )
        return _ok("crypto", summary, coin=coin, prices=row)
    except Exception as exc:
        return _err("crypto", str(exc))


def tool_joke() -> Dict[str, Any]:
    try:
        data = _http_json(
            "https://official-joke-api.appspot.com/random_joke",
        )
        setup = data.get("setup") or ""
        punch = data.get("punchline") or ""
        return _ok("joke", f"{setup} — {punch}", setup=setup, punchline=punch)
    except Exception:
        return _ok(
            "joke",
            "Why do programmers prefer dark mode? Because light attracts bugs.",
            offline=True,
        )


def tool_uuid() -> Dict[str, Any]:
    import uuid

    u = str(uuid.uuid4())
    return _ok("uuid", u, value=u)


def tool_qr_url(text: str) -> Dict[str, Any]:
    """Return a QR image URL (no local render needed)."""
    text = (text or "").strip()
    if not text:
        return _err("qr", "text required")
    if len(text) > 500:
        return _err("qr", "text too long (max 500)")
    img = "https://api.qrserver.com/v1/create-qr-code/?" + urllib.parse.urlencode(
        {"size": "220x220", "data": text}
    )
    return _ok("qr", f"QR code URL for your text:\n{img}", image_url=img, data=text)


# --- registry ---------------------------------------------------------------

ToolFn = Callable[..., Dict[str, Any]]

TOOLS: Dict[str, Dict[str, Any]] = {
    "web_search": {
        "name": "web_search",
        "title": "Web search",
        "wow": True,
        "description": "Search the web (Google CSE if configured, else DuckDuckGo).",
        "args": {"query": "string", "max_results": "int?"},
        "fn": tool_web_search,
        "chip": "Search",
        "prompt_hint": "search for ",
    },
    "wikipedia": {
        "name": "wikipedia",
        "title": "Wikipedia",
        "wow": True,
        "description": "Quick encyclopedia summary.",
        "args": {"query": "string"},
        "fn": tool_wikipedia,
        "chip": "Wiki",
        "prompt_hint": "wikipedia ",
    },
    "weather": {
        "name": "weather",
        "title": "Weather",
        "wow": True,
        "description": "Current weather for a place (wttr.in).",
        "args": {"place": "string"},
        "fn": tool_weather,
        "chip": "Weather",
        "prompt_hint": "weather in ",
    },
    "define": {
        "name": "define",
        "title": "Define",
        "wow": True,
        "description": "English dictionary definition.",
        "args": {"word": "string"},
        "fn": tool_define,
        "chip": "Define",
        "prompt_hint": "define ",
    },
    "calc": {
        "name": "calc",
        "title": "Calculator",
        "wow": True,
        "description": "Safe math (sqrt, sin, +, *, etc.).",
        "args": {"expression": "string"},
        "fn": tool_calc,
        "chip": "Calc",
        "prompt_hint": "calc ",
    },
    "time_now": {
        "name": "time_now",
        "title": "World clock",
        "wow": True,
        "description": "Current time (optional IANA timezone).",
        "args": {"tz": "string?"},
        "fn": tool_time_now,
        "chip": "Time",
        "prompt_hint": "what time is it",
    },
    "translate": {
        "name": "translate",
        "title": "Translate",
        "wow": True,
        "description": "Translate text (MyMemory).",
        "args": {"text": "string", "to": "string?", "fr": "string?"},
        "fn": tool_translate,
        "chip": "Translate",
        "prompt_hint": "translate to es: ",
    },
    "news": {
        "name": "news",
        "title": "News",
        "wow": True,
        "description": "Quick news search for a topic.",
        "args": {"topic": "string?"},
        "fn": tool_news,
        "chip": "News",
        "prompt_hint": "news about ",
    },
    "crypto": {
        "name": "crypto",
        "title": "Crypto price",
        "wow": True,
        "description": "Live crypto price (CoinGecko).",
        "args": {"symbol": "string?"},
        "fn": tool_crypto,
        "chip": "Crypto",
        "prompt_hint": "btc price",
    },
    "joke": {
        "name": "joke",
        "title": "Joke",
        "wow": False,
        "description": "A quick joke.",
        "args": {},
        "fn": tool_joke,
        "chip": "Joke",
        "prompt_hint": "tell me a joke",
    },
    "uuid": {
        "name": "uuid",
        "title": "UUID",
        "wow": False,
        "description": "Generate a random UUID.",
        "args": {},
        "fn": tool_uuid,
        "chip": "UUID",
        "prompt_hint": "generate a uuid",
    },
    "qr": {
        "name": "qr",
        "title": "QR code",
        "wow": True,
        "description": "Make a QR code image URL for text/link.",
        "args": {"text": "string"},
        "fn": tool_qr_url,
        "chip": "QR",
        "prompt_hint": "qr code for ",
    },
}


def catalog() -> Dict[str, Any]:
    google_oauth.load_dotenv()
    has_google_search = bool(
        (os.environ.get("GOOGLE_CSE_ID") or "").strip()
        and (os.environ.get("GOOGLE_API_KEY") or "").strip()
    )
    tools = []
    for t in TOOLS.values():
        tools.append(
            {
                "name": t["name"],
                "title": t["title"],
                "description": t["description"],
                "args": t["args"],
                "wow": t.get("wow", False),
                "chip": t.get("chip"),
                "prompt_hint": t.get("prompt_hint"),
            }
        )
    return {
        "ok": True,
        "tools": tools,
        "google_search": has_google_search,
        "search_provider": "google_cse" if has_google_search else "duckduckgo",
    }


def run_tool(name: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    name = (name or "").strip().lower()
    args = args or {}
    meta = TOOLS.get(name)
    if not meta:
        return _err(name or "unknown", f"Unknown tool “{name}”. Use GET /api/tools.")
    fn: ToolFn = meta["fn"]
    try:
        # Map common aliases
        if name == "web_search":
            return fn(args.get("query") or args.get("q") or "", args.get("max_results", 5))
        if name == "wikipedia":
            return fn(args.get("query") or args.get("q") or args.get("title") or "")
        if name == "weather":
            return fn(args.get("place") or args.get("location") or args.get("q") or "")
        if name == "define":
            return fn(args.get("word") or args.get("q") or "")
        if name == "calc":
            return fn(args.get("expression") or args.get("expr") or args.get("q") or "")
        if name == "time_now":
            return fn(args.get("tz") or args.get("timezone") or "")
        if name == "translate":
            return fn(
                args.get("text") or args.get("q") or "",
                args.get("to") or args.get("target") or "en",
                args.get("fr") or args.get("from") or "auto",
            )
        if name == "news":
            return fn(args.get("topic") or args.get("q") or "world")
        if name == "crypto":
            return fn(args.get("symbol") or args.get("coin") or args.get("q") or "bitcoin")
        if name == "joke":
            return fn()
        if name == "uuid":
            return fn()
        if name == "qr":
            return fn(args.get("text") or args.get("q") or args.get("data") or "")
        return fn(**args)
    except TypeError as exc:
        return _err(name, f"Bad args: {exc}")
    except Exception as exc:
        return _err(name, str(exc))


# Intent heuristics for chat (fast path before/without model tool JSON)
_INTENT_PATTERNS: List[Tuple[re.Pattern[str], str, Callable[[re.Match[str]], Dict[str, Any]]]] = [
    (
        re.compile(r"^(?:search|google|look up|find)\s+(?:for\s+)?(.+)$", re.I),
        "web_search",
        lambda m: {"query": m.group(1).strip()},
    ),
    (
        re.compile(r"^(?:wiki|wikipedia)\s+(.+)$", re.I),
        "wikipedia",
        lambda m: {"query": m.group(1).strip()},
    ),
    (
        re.compile(r"^(?:weather|forecast)(?:\s+(?:in|for|at))?\s+(.+)$", re.I),
        "weather",
        lambda m: {"place": m.group(1).strip()},
    ),
    (
        re.compile(r"^(?:define|definition of|what does)\s+['\"]?(.+?)['\"]?\s+mean\??$", re.I),
        "define",
        lambda m: {"word": m.group(1).strip()},
    ),
    (
        re.compile(r"^(?:define)\s+(.+)$", re.I),
        "define",
        lambda m: {"word": m.group(1).strip()},
    ),
    (
        re.compile(r"^(?:calc|calculate|compute)\s+(.+)$", re.I),
        "calc",
        lambda m: {"expression": m.group(1).strip()},
    ),
    (
        re.compile(r"^(?:what(?:'s| is)\s+)?(?:the\s+)?time(?:\s+in\s+(\S+))?[\s?]*$", re.I),
        "time_now",
        lambda m: {"tz": (m.group(1) or "").strip()},
    ),
    (
        re.compile(
            r"^translate(?:\s+to\s+(\w+))?(?:\s+from\s+(\w+))?\s*:\s*(.+)$",
            re.I,
        ),
        "translate",
        lambda m: {
            "to": (m.group(1) or "en").strip(),
            "fr": (m.group(2) or "auto").strip(),
            "text": m.group(3).strip(),
        },
    ),
    (
        re.compile(r"^(?:news)(?:\s+(?:about|on|for))?\s*(.*)$", re.I),
        "news",
        lambda m: {"topic": (m.group(1) or "world").strip() or "world"},
    ),
    (
        re.compile(
            r"^(?:crypto|price of|how much is)\s+(\w+)(?:\s+price)?[\s?]*$",
            re.I,
        ),
        "crypto",
        lambda m: {"symbol": m.group(1).strip()},
    ),
    (
        re.compile(r"^(?:btc|eth|sol)\s*(?:price)?[\s?]*$", re.I),
        "crypto",
        lambda m: {"symbol": m.group(0).split()[0]},
    ),
    (
        re.compile(r"^(?:tell me a )?joke[\s!?.]*$", re.I),
        "joke",
        lambda _m: {},
    ),
    (
        re.compile(r"^(?:uuid|generate (?:a )?uuid)[\s?]*$", re.I),
        "uuid",
        lambda _m: {},
    ),
    (
        re.compile(r"^(?:qr|qr code)(?:\s+for)?\s+(.+)$", re.I),
        "qr",
        lambda m: {"text": m.group(1).strip()},
    ),
]


def detect_intent(message: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    text = (message or "").strip()
    if not text:
        return None
    for pattern, name, arg_fn in _INTENT_PATTERNS:
        m = pattern.match(text)
        if m:
            return name, arg_fn(m)
    # bare math like "2+2" or "sqrt(9)"
    if re.fullmatch(r"[\d\.\s\+\-\*/\(\)%eEsqrtsincotanlogpi,_]+", text) and any(
        c in text for c in "+-*/%"
    ):
        return "calc", {"expression": text}
    return None


_TOOL_JSON_RE = re.compile(
    r"TOOL\s*:\s*(\{.*?\})\s*$",
    re.I | re.S,
)


def parse_tool_directive(model_text: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Parse trailing TOOL: {...} from model output."""
    text = (model_text or "").strip()
    m = _TOOL_JSON_RE.search(text)
    if not m:
        # also allow ```tool ... ```
        m2 = re.search(
            r"```tool\s*(\{.*?\})\s*```",
            text,
            flags=re.I | re.S,
        )
        if not m2:
            return None
        raw = m2.group(1)
    else:
        raw = m.group(1)
    try:
        data = json.loads(raw)
    except Exception:
        return None
    name = (data.get("name") or data.get("tool") or "").strip()
    args = data.get("args") or data.get("arguments") or {}
    if not name:
        return None
    if not isinstance(args, dict):
        args = {"q": str(args)}
    return name, args


def strip_tool_directive(model_text: str) -> str:
    text = _TOOL_JSON_RE.sub("", model_text or "").strip()
    text = re.sub(r"```tool\s*\{.*?\}\s*```", "", text, flags=re.I | re.S).strip()
    return text


def tools_system_addon() -> str:
    names = ", ".join(TOOLS.keys())
    return (
        "You have PC-side tools. For live facts (search, weather, wiki, news, "
        "crypto, definitions, time, translate, calc), either answer from tool "
        "results the user already provided, OR request ONE tool by ending your "
        f"reply with exactly: TOOL: {{\"name\":\"web_search\",\"args\":{{\"query\":\"...\"}}}} "
        f"Available tools: {names}. Prefer tools for current events and weather. "
        "Do not invent live prices or headlines."
    )
