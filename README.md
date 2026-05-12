# DataHarvest — Web Scraper for Dataset Creation

A Flask-powered web scraper that turns any public webpage into a structured CSV/JSON dataset.

---

## Project Structure

```
web-scraper/
├── app.py                 # Flask app, routes, REST API
├── requirements.txt
├── .env                   # environment variables (edit before running)
├── scraper/
│   ├── __init__.py
│   └── scraper.py         # all scraping logic
├── templates/
│   ├── index.html         # input form
│   └── results.html       # results table + download
├── static/
│   └── styles.css
├── data/                  # auto-created — CSV, JSON, images saved here
└── logs/                  # auto-created — scraper.log
```

---

## Quick Start

### 1. Clone / download the project

```bash
cd web-scraper
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables (optional)

Edit `.env` — defaults work fine for local development.

### 5. Run

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

---

## Features

| Feature | Details |
|---|---|
| HTML element scraping | Pick any tag (`h2`, `div`, `span`, `a`, …) and optional CSS class |
| Pagination | Follow "next" links automatically (up to 5 pages) |
| Image scraping | Download images locally with a single toggle |
| Data cleaning | Deduplication + whitespace normalisation |
| CSV download | One-click export from results page |
| JSON export | Saved alongside CSV in `data/` |
| REST API | `POST /api/scrape` — see below |
| Logging | Rotating log at `logs/scraper.log` |

---

## REST API

```
POST /api/scrape
Content-Type: application/json
```

**Body**

```json
{
  "url":           "https://quotes.toscrape.com",
  "tag":           "span",
  "class_name":    "text",
  "max_pages":     2,
  "scrape_images": false
}
```

**Response**

```json
{
  "total": 20,
  "pages_scraped": 2,
  "errors": [],
  "records": [ { "text": "...", "tag": "span", ... } ],
  "file_paths": { "csv": "data/dataset_20240101_120000.csv", "json": "..." }
}
```

---

## Test URLs

| URL | Tag | Class | Notes |
|---|---|---|---|
| https://books.toscrape.com | `h3` | _(empty)_ | Book titles |
| https://quotes.toscrape.com | `span` | `text` | Famous quotes |
| https://news.ycombinator.com | `span` | `titleline` | HN headlines |
| https://realpython.com | `h2` | _(empty)_ | Article headings |
| https://en.wikipedia.org/wiki/Python_(programming_language) | `h2` | _(empty)_ | Section headings |

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_DEBUG` | `true` | Enable Flask debug mode |
| `SECRET_KEY` | `dev-secret-change-me` | Flask session secret |
| `PORT` | `5000` | Port to listen on |
| `SCRAPER_TIMEOUT` | `15` | HTTP request timeout (seconds) |
| `MAX_PAGES` | `5` | Maximum pages to paginate |

---

## Dependencies

- **Flask** — web framework
- **requests** — HTTP client
- **BeautifulSoup4 + lxml** — HTML parsing
- **pandas** — data structuring & CSV export
- **python-dotenv** — `.env` loading
