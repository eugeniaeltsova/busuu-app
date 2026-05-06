"""
scraper/busuu_api.py

Fetches vocabulary and grammar data from Busuu's internal API using
the access-token cookie exported from a real browser session.

Endpoints used:
  GET /users/me                                          → user profile
  GET /vocabulary/all/{lang}?translations={lang},en      → vocabulary
  GET /api/grammar/progress?language={lang}              → grammar mastery
  GET /api/v2/component/grammar_review_{lang}            → grammar topic names
  GET /api/v2/progress/{lang}                            → course progress
"""
from __future__ import annotations

import asyncio
import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

BASE = "https://api.busuu.com"


async def _get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params=None,
    retries: int = 3,
) -> httpx.Response:
    """GET with exponential backoff. Raises PermissionError on 401/403, retries on 5xx and network errors."""
    delay = 1.0
    last_exc: Exception = RuntimeError(f"No attempts made for {url}")
    for attempt in range(retries):
        try:
            r = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            logger.warning("Network error for %s (attempt %d/%d): %s", url, attempt + 1, retries, exc)
            last_exc = exc
        else:
            if r.status_code in (401, 403):
                raise PermissionError("Busuu session expired — please re-export your cookies.")
            if r.status_code < 500:
                return r
            logger.warning("Server error %s for %s (attempt %d/%d)", r.status_code, url, attempt + 1, retries)
            last_exc = RuntimeError(f"Server error {r.status_code}")
        if attempt < retries - 1:
            await asyncio.sleep(delay)
            delay *= 2
    raise last_exc
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.busuu.com/",
    "Origin":          "https://www.busuu.com",
}


def load_cookies(cookie_file: str) -> dict[str, str]:
    raw = json.loads(Path(cookie_file).read_text())
    return {c["name"]: c["value"] for c in raw if "busuu.com" in c.get("domain", "")}


def extract_user_info(cookies: dict[str, str]) -> tuple[str, int]:
    import base64
    token = cookies.get("access-token", "")
    if not token:
        raise RuntimeError("No access-token in cookies. Re-export from browser.")
    payload = token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    data = json.loads(base64.b64decode(payload))
    return data["sub"], data["data"]["user_legacy_id"]


def normalise_vocab(raw_data: dict, native_lang: str = "en", target_lang: str = "es") -> list[dict]:
    """
    Join vocabulary + entity_map + translation_map into flat word records.

    vocab item:      {"entity_id": "entity__9f850a0a", "strength": 0, ...}
    entity_map:      {"entity__9f850a0a": {"phrase": "str_xxx", "image": "..."}}
    translation_map: {"str_xxx": {"es": {"value": "lavabo"}, "en": {"value": "sink"}}}
    """
    vocabulary      = raw_data.get("vocabulary", [])
    entity_map      = raw_data.get("entity_map", {})
    translation_map = raw_data.get("translation_map", {})

    normalised = []
    for item in vocabulary:
        entity_id = item.get("entity_id", "")
        entity    = entity_map.get(entity_id, {})

        phrase_id    = entity.get("phrase") or entity.get("keyphrase", "")
        keyphrase_id = entity.get("keyphrase") or entity.get("phrase", "")

        phrase_trans    = translation_map.get(phrase_id, {})
        keyphrase_trans = translation_map.get(keyphrase_id, {})

        target_word = (phrase_trans.get(target_lang) or {}).get("value", "")
        native_word = (phrase_trans.get(native_lang) or {}).get("value", "")

        if not target_word:
            target_word = (keyphrase_trans.get(target_lang) or {}).get("value", "")
        if not native_word:
            native_word = (keyphrase_trans.get(native_lang) or {}).get("value", "")

        strength     = item.get("strength", 0)
        strength_norm = round(strength / 5.0, 3) if strength else 0.0

        update_ts    = item.get("update_time")
        last_reviewed = (
            datetime.fromtimestamp(update_ts, tz=timezone.utc).isoformat()
            if update_ts else None
        )

        target_word = target_word.strip().lstrip("¿¡").rstrip("?!")
        target_word = (target_word[0].lower() + target_word[1:]) if target_word else ""

        normalised.append({
            "busuu_item_id": str(item.get("id", "")),
            "entity_id":     entity_id,
            "word":          target_word,
            "translation":   native_word,
            "image_url":     entity.get("image", ""),
            "strength":      strength_norm,
            "strength_raw":  strength,
            "saved":         item.get("saved", False),
            "last_reviewed": last_reviewed,
            "raw":           item,
        })

    normalised.sort(key=lambda x: x["strength"])
    return normalised


def normalise_grammar(grammar_list: list, grammar_component: dict | None = None, native_lang: str = "en") -> list[dict]:    
    """
    Map grammar/progress topic IDs to human-readable names using
    the grammar_review component's translation_map.
    """
    topic_meta: dict[str, dict] = {}

    if grammar_component:
        tmap = grammar_component.get("translation_map", {})

        def resolve(str_id: str) -> str:
            entry = tmap.get(str_id, {})
            value = (entry.get(native_lang) or {}).get("value", "")
            if not value:
                value = (entry.get("en") or {}).get("value", "")
            return value or str_id

        for cat in grammar_component.get("grammar_categories", []):
            cat_name = resolve(cat.get("content", {}).get("name", ""))
            for topic in cat.get("grammar_topics", []):
                topic_id   = topic.get("id", "")
                topic_name = resolve(topic.get("content", {}).get("name", ""))
                level      = topic.get("content", {}).get("level", "")
                topic_meta[topic_id] = {
                    "name":     topic_name,
                    "category": cat_name,
                    "level":    level.upper() if level else "",
                }

    normalised = []
    for item in grammar_list:
        topic_id = item.get("topic_id", "")
        meta     = topic_meta.get(topic_id, {})
        strength = item.get("strength", 0)

        normalised.append({
            "busuu_topic_id": topic_id,
            "unit_name":      meta.get("name") or topic_id,
            "topic_name":     meta.get("category", ""),
            "cert_level":     meta.get("level", ""),
            "strength":       strength,
            "strength_norm":  round(strength / 4.0, 3),
            "percentage":     item.get("percentage", 0),
            "completed":      strength >= 2,
            "raw":            item,
        })

    normalised.sort(key=lambda x: x["strength"])
    return normalised


async def fetch_all(cookie_file: str, language: str = "es", native_lang: str = "en") -> dict:
    cookies = load_cookies(cookie_file)
    user_uuid, user_legacy_id = extract_user_info(cookies)
    logger.info("User UUID: %s  |  Legacy ID: %s", user_uuid, user_legacy_id)

    raw: dict = {
        "user_uuid":         user_uuid,
        "user_legacy_id":    user_legacy_id,
        "user":              {},
        "vocab_raw":         {},
        "grammar_raw":       [],
        "grammar_component": {},
        "course_progress":   {},
    }

    async with httpx.AsyncClient(
        headers=HEADERS, cookies=cookies, timeout=60, follow_redirects=True,
    ) as client:

        r = await _get_with_retry(client, f"{BASE}/users/me")
        if r.status_code == 200:
            raw["user"] = r.json().get("data", r.json())
            logger.info("✓ user: %s", raw["user"].get("username", user_uuid))
        else:
            logger.warning("✗ /users/me → %s", r.status_code)

        r = await _get_with_retry(
            client, f"{BASE}/vocabulary/all/{language}",
            params={"translations": f"{language},{native_lang}"},
        )
        if r.status_code == 200:
            raw["vocab_raw"] = r.json().get("data", {})
            logger.info("✓ vocab: %d items", len(raw["vocab_raw"].get("vocabulary", [])))
        else:
            logger.warning("✗ vocabulary → %s", r.status_code)

        r = await _get_with_retry(client, f"{BASE}/api/grammar/progress", params={"language": language})
        if r.status_code == 200:
            raw["grammar_raw"] = r.json().get("data", [])
            logger.info("✓ grammar: %d topics", len(raw["grammar_raw"]))
        else:
            logger.warning("✗ grammar/progress → %s", r.status_code)

        r = await _get_with_retry(
            client, f"{BASE}/api/v2/component/grammar_review_{language}",
            params={"language": language, "translations": native_lang, "depth": "2"},
        )
        if r.status_code == 200:
            raw["grammar_component"] = r.json()
            logger.info("✓ grammar component fetched")
        else:
            logger.warning("✗ grammar component → %s", r.status_code)

        r = await _get_with_retry(client, f"{BASE}/api/v2/progress/{language}")
        if r.status_code == 200:
            data = r.json()
            raw["course_progress"] = data.get("data", data) if isinstance(data, dict) else data
            logger.info("✓ course progress fetched")
        else:
            logger.warning("✗ course progress → %s", r.status_code)

    vocab   = normalise_vocab(raw["vocab_raw"], native_lang=native_lang)
    grammar = normalise_grammar(raw["grammar_raw"], raw.get("grammar_component"), native_lang=native_lang)
    logger.info("Normalised: %d vocab, %d grammar topics", len(vocab), len(grammar))

    return {
        "user_uuid":       user_uuid,
        "user_legacy_id":  user_legacy_id,
        "user":            raw["user"],
        "vocab":           vocab,
        "grammar":         grammar,
        "course_progress": raw["course_progress"],
    }


async def main(cookie_file: str, out: str, language: str) -> None:
    results = await fetch_all(cookie_file, language)

    print("\n" + "=" * 60)
    print("FETCH RESULTS")
    print("=" * 60)
    print(f"User:           {results['user'].get('username') or results['user_uuid']}")
    print(f"Vocab items:    {len(results['vocab'])}")
    print(f"Grammar topics: {len(results['grammar'])}")

    if results["vocab"]:
        print("\n-- Weakest vocab (first 3) --")
        for item in results["vocab"][:3]:
            print(f"  {item['word']!r:35} → {item['translation']!r:35}  strength={item['strength_raw']}/5")

    if results["grammar"]:
        print("\n-- Weakest grammar topics (first 3) --")
        for t in results["grammar"][:3]:
            print(f"  {t['unit_name']!r:50}  strength={t['strength']}/4  {t['percentage']}%")

    Path(out).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nFull dump saved to: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookies",  default="busuu_cookies.json")
    parser.add_argument("--language", default="es")
    parser.add_argument("--out",      default="api_dump.json")
    args = parser.parse_args()
    asyncio.run(main(args.cookies, args.out, args.language))
