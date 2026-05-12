"""
scraper/scraper.py
Core scraping logic: fetch pages, parse HTML, clean data, save files.
"""

import os
import re
import json
import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "scraper.log")),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", 15))
MAX_PAGES = int(os.getenv("MAX_PAGES", 5))
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
IMAGES_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _validate_url(url: str) -> str:
    """Ensure the URL has a scheme; raise ValueError if invalid."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def _fetch_page(url: str, session: requests.Session) -> BeautifulSoup | None:
    """Fetch a single page and return a BeautifulSoup object, or None on error."""
    try:
        resp = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        logger.info("Fetched %s [%d]", url, resp.status_code)
        return BeautifulSoup(resp.text, "html.parser")
    except requests.exceptions.ConnectionError:
        logger.error("Connection error fetching %s", url)
    except requests.exceptions.Timeout:
        logger.error("Timeout fetching %s", url)
    except requests.exceptions.HTTPError as exc:
        logger.error("HTTP %s for %s", exc.response.status_code, url)
    except Exception as exc:
        logger.error("Unexpected error fetching %s: %s", url, exc)
    return None


def _find_next_page(soup: BeautifulSoup, base_url: str) -> str | None:
    """Try to detect a 'next page' link."""
    for selector in [
        {"rel": "next"},
        {"aria-label": re.compile(r"next", re.I)},
        {"class": re.compile(r"next", re.I)},
        {"id": re.compile(r"next", re.I)},
    ]:
        tag = soup.find("a", selector)
        if tag and tag.get("href"):
            return urljoin(base_url, tag["href"])

    # Fallback: look for anchor whose text says "next"
    for a in soup.find_all("a", string=re.compile(r"next", re.I)):
        if a.get("href"):
            return urljoin(base_url, a["href"])

    return None


def _clean_text(text: str) -> str:
    """Strip whitespace and collapse internal spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _scrape_elements(soup: BeautifulSoup, tag: str, class_name: str, base_url: str) -> list[dict]:
    """Extract matching elements from a parsed page."""
    kwargs = {}
    if class_name:
        kwargs["class_"] = class_name

    elements = soup.find_all(tag, **kwargs) if tag else []

    results = []
    for el in elements:
        text = _clean_text(el.get_text())
        if not text:
            continue

        item = {
            "text": text,
            "tag": el.name,
            "class": " ".join(el.get("class", [])),
            "href": urljoin(base_url, el.get("href", "")) if el.get("href") else "",
            "src": urljoin(base_url, el.get("src", "")) if el.get("src") else "",
        }
        results.append(item)

    return results


def _scrape_images(soup: BeautifulSoup, base_url: str, save: bool = True) -> list[dict]:
    """Download all images on the page and return metadata."""
    images = []
    session = requests.Session()

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue
        full_url = urljoin(base_url, src)
        alt = _clean_text(img.get("alt", ""))
        record = {"url": full_url, "alt": alt, "local_path": ""}

        if save:
            try:
                r = session.get(full_url, headers=HEADERS, timeout=TIMEOUT)
                r.raise_for_status()
                ext = os.path.splitext(urlparse(full_url).path)[-1] or ".jpg"
                filename = re.sub(r"[^\w]", "_", full_url[-40:]) + ext
                filepath = os.path.join(IMAGES_DIR, filename)
                with open(filepath, "wb") as f:
                    f.write(r.content)
                record["local_path"] = filepath
                logger.info("Saved image: %s", filename)
            except Exception as exc:
                logger.warning("Could not download image %s: %s", full_url, exc)

        images.append(record)

    return images


def _save_data(records: list[dict], timestamp: str) -> dict[str, str]:
    """Persist records to CSV and JSON; return file paths."""
    paths = {}
    if not records:
        return paths

    df = pd.DataFrame(records)

    csv_path = os.path.join(DATA_DIR, f"dataset_{timestamp}.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    paths["csv"] = csv_path
    logger.info("Saved CSV: %s (%d rows)", csv_path, len(df))

    json_path = os.path.join(DATA_DIR, f"dataset_{timestamp}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    paths["json"] = json_path
    logger.info("Saved JSON: %s", json_path)

    return paths


# ── Public API ────────────────────────────────────────────────────────────────

def scrape(
    url: str,
    tag: str = "p",
    class_name: str = "",
    max_pages: int = 1,
    scrape_images: bool = False,
) -> dict:
    """
    Main scrape entry-point.

    Parameters
    ----------
    url          : Starting URL.
    tag          : HTML tag to scrape (e.g. 'h2', 'div', 'span').
    class_name   : Optional CSS class filter.
    max_pages    : How many paginated pages to follow (1 = no pagination).
    scrape_images: Whether to download images.

    Returns
    -------
    dict with keys: records, images, file_paths, pages_scraped, errors
    """
    url = _validate_url(url)
    max_pages = min(max_pages, MAX_PAGES)

    all_records: list[dict] = []
    all_images: list[dict] = []
    errors: list[str] = []
    pages_scraped = 0
    current_url: str | None = url

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with requests.Session() as session:
        while current_url and pages_scraped < max_pages:
            logger.info("Scraping page %d: %s", pages_scraped + 1, current_url)
            soup = _fetch_page(current_url, session)

            if soup is None:
                errors.append(f"Failed to fetch: {current_url}")
                break

            # Scrape elements
            page_records = _scrape_elements(soup, tag, class_name, current_url)
            for rec in page_records:
                rec["source_url"] = current_url
                rec["page"] = pages_scraped + 1
            all_records.extend(page_records)

            # Optionally scrape images
            if scrape_images:
                page_images = _scrape_images(soup, current_url, save=True)
                all_images.extend(page_images)

            pages_scraped += 1

            # Pagination
            if pages_scraped < max_pages:
                current_url = _find_next_page(soup, current_url)
            else:
                current_url = None

    # Clean duplicates
    seen = set()
    unique_records = []
    for rec in all_records:
        key = rec.get("text", "")
        if key and key not in seen:
            seen.add(key)
            unique_records.append(rec)

    logger.info(
        "Done. %d records (%d duplicates removed) across %d page(s).",
        len(unique_records),
        len(all_records) - len(unique_records),
        pages_scraped,
    )

    # Save
    file_paths = _save_data(unique_records, timestamp)

    return {
        "records": unique_records,
        "images": all_images,
        "file_paths": file_paths,
        "pages_scraped": pages_scraped,
        "errors": errors,
        "timestamp": timestamp,
    }
