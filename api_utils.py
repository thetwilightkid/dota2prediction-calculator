import os
import time

import cloudscraper
import requests
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(ROOT_DIR, ".env"))
OPENDOTA_API_KEY = os.getenv("OPENDOTA_API_KEY")
STRATZ_TOKEN = os.getenv("STRATZ_TOKEN")
STRATZ_URL = "https://api.stratz.com/graphql"
_stratz_scraper = cloudscraper.create_scraper()

# Once the free tier's daily quota is confirmed exhausted, remember it for the
# rest of the process so every subsequent call doesn't waste a round-trip
# re-discovering the same thing before falling back to the paid key.
_free_tier_exhausted = False


class RateLimitExceeded(Exception):
    pass


def openDotaGet(url, params=None, max_retries=3, retry_sleep=3, timeout=15):
    """GET against OpenDota, using the free tier by default and only
    attaching the paid API key once the free tier's daily quota is hit."""
    global _free_tier_exhausted
    params = dict(params or {})
    if _free_tier_exhausted and OPENDOTA_API_KEY:
        params["api_key"] = OPENDOTA_API_KEY

    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=params, timeout=timeout).json()
        except requests.exceptions.RequestException as e:
            print(f"    Сетевая ошибка (попытка {attempt + 1}/{max_retries}): {e}")
            time.sleep(retry_sleep)
            continue

        is_rate_limited = isinstance(response, dict) and "api limit" in str(response.get("error", "")).lower()
        if is_rate_limited:
            if OPENDOTA_API_KEY and "api_key" not in params:
                print("    Дневной лимит бесплатного тарифа исчерпан, переключаемся на платный ключ...")
                params["api_key"] = OPENDOTA_API_KEY
                _free_tier_exhausted = True
                continue
            print(f"    Ограничение запросов (попытка {attempt + 1}/{max_retries}): {response}")
            time.sleep(retry_sleep)
            continue

        return response

    raise RateLimitExceeded(f"Exhausted retries for {url}")


class StratzUnavailable(Exception):
    pass


def stratzPost(query, max_retries=5, retry_sleep=5, timeout=20):
    """POST a GraphQL query to Stratz, retrying on network errors, non-200
    responses (e.g. transient 503s) and malformed JSON. Returns the parsed
    response dict (with a top-level "data" key), same shape as a raw
    scraper.post(...).json() call - caller still does data['data']['match']
    etc. themselves."""
    for attempt in range(max_retries):
        try:
            r = _stratz_scraper.post(
                STRATZ_URL,
                json={"query": query},
                headers={"Authorization": f"Bearer {STRATZ_TOKEN}"},
                timeout=timeout,
            )
        except requests.exceptions.RequestException as e:
            print(f"    Stratz: сетевая ошибка (попытка {attempt + 1}/{max_retries}): {e}")
            time.sleep(retry_sleep)
            continue

        if r.status_code != 200:
            print(f"    Stratz: HTTP {r.status_code} (попытка {attempt + 1}/{max_retries}): {r.text[:200]}")
            time.sleep(retry_sleep)
            continue

        try:
            return r.json()
        except ValueError:
            print(f"    Stratz: невалидный JSON в ответе (попытка {attempt + 1}/{max_retries})")
            time.sleep(retry_sleep)
            continue

    raise StratzUnavailable(f"Stratz unavailable after {max_retries} attempts")
