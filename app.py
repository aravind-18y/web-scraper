"""
app.py  —  Web Scraper for Dataset Creation
Flask application: serves the UI and exposes a REST API.
"""

import os
import logging
from pathlib import Path
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    send_file,
    redirect,
    url_for,
    flash,
    session,
)
from scraper import scrape

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

logger = logging.getLogger(__name__)

# ── Routes ────────────────────────────────────────────────────────────────────


@app.route("/", methods=["GET"])
def index():
    """Render the main input form."""
    return render_template("index.html")


@app.route("/scrape", methods=["POST"])
def scrape_view():
    """
    Handle form submission:
    - Validate inputs
    - Call the scraper
    - Redirect to results page
    """
    url = request.form.get("url", "").strip()
    tag = request.form.get("tag", "p").strip() or "p"
    class_name = request.form.get("class_name", "").strip()
    max_pages = int(request.form.get("max_pages", 1))
    scrape_images = request.form.get("scrape_images") == "on"

    if not url:
        flash("Please enter a URL.", "danger")
        return redirect(url_for("index"))

    try:
        result = scrape(
            url=url,
            tag=tag,
            class_name=class_name,
            max_pages=max_pages,
            scrape_images=scrape_images,
        )
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("index"))
    except Exception as exc:
        logger.exception("Unexpected error during scrape")
        flash(f"Unexpected error: {exc}", "danger")
        return redirect(url_for("index"))

    # Store lightweight metadata in session; pass full records via template
    session["last_timestamp"] = result.get("timestamp")
    session["last_csv"] = result["file_paths"].get("csv", "")

    return render_template(
        "results.html",
        records=result["records"][:500],       # cap display at 500 rows
        total=len(result["records"]),
        images=result["images"],
        pages_scraped=result["pages_scraped"],
        errors=result["errors"],
        file_paths=result["file_paths"],
        url=url,
        tag=tag,
        class_name=class_name,
    )


@app.route("/download")
def download():
    """Stream the most-recently-generated CSV to the browser."""
    csv_path = session.get("last_csv", "")
    if not csv_path or not Path(csv_path).exists():
        flash("No dataset available for download.", "warning")
        return redirect(url_for("index"))
    return send_file(csv_path, as_attachment=True, mimetype="text/csv")


# ── REST API ──────────────────────────────────────────────────────────────────


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    """
    POST /api/scrape
    Body (JSON): { url, tag, class_name, max_pages, scrape_images }
    Returns JSON with records and metadata.
    """
    data = request.get_json(force=True, silent=True) or {}

    url = data.get("url", "").strip()
    tag = data.get("tag", "p").strip() or "p"
    class_name = data.get("class_name", "").strip()
    max_pages = int(data.get("max_pages", 1))
    scrape_images = bool(data.get("scrape_images", False))

    if not url:
        return jsonify({"error": "url is required"}), 400

    try:
        result = scrape(
            url=url,
            tag=tag,
            class_name=class_name,
            max_pages=max_pages,
            scrape_images=scrape_images,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        logger.exception("API scrape error")
        return jsonify({"error": f"Internal error: {exc}"}), 500

    return jsonify(
        {
            "total": len(result["records"]),
            "pages_scraped": result["pages_scraped"],
            "errors": result["errors"],
            "records": result["records"],
            "file_paths": {k: str(v) for k, v in result["file_paths"].items()},
        }
    )


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    port = int(os.getenv("PORT", 5000))
    app.run(debug=debug, port=port)
