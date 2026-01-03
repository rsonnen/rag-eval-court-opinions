#!/usr/bin/env python
"""Download court opinions from CourtListener for RAG evaluation.

A general-purpose CLI tool that downloads court opinion PDFs from CourtListener
based on search queries. Handles rate limits with exponential backoff, supports
resumable downloads, and saves metadata alongside PDFs.

Usage:
    uv run python download_opinions.py "patent infringement" --corpus patent_cases --max-docs 150
    uv run python download_opinions.py "Clean Water Act" --corpus environmental --max-docs 200
    uv run python download_opinions.py "asylum deportation" --corpus immigration

Output:
    <data-dir>/<corpus>/
        opinions/       - PDF files named by opinion ID
        metadata.json   - Opinion metadata for all downloaded documents

API Notes:
    - Search: GET https://www.courtlistener.com/api/rest/v4/search/?q=<query>&type=o
    - PDFs: https://storage.courtlistener.com/<local_path> (public, no auth)
    - CourtListener is a nonprofit - be respectful with rate limits
"""

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

COURTLISTENER_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
COURTLISTENER_STORAGE_URL = "https://storage.courtlistener.com"

# Rate limiting configuration - CourtListener is a small nonprofit, be very gentle
BASE_DELAY_SECONDS = 3.0  # Minimum delay between requests (conservative)
MAX_RETRIES = 8  # Maximum retries on 429/5xx errors
BACKOFF_FACTOR = 2.5  # Exponential backoff multiplier
MAX_BACKOFF_SECONDS = 300  # Maximum backoff delay (5 minutes)


def request_with_retry(
    client: httpx.Client,
    url: str,
    params: dict[str, Any] | None = None,
    *,
    follow_redirects: bool = False,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff on rate limit/server errors.

    Args:
        client: HTTP client for requests.
        url: URL to request.
        params: Optional query parameters.
        follow_redirects: Whether to follow redirects.

    Returns:
        HTTP response.

    Raises:
        httpx.HTTPError: If all retries are exhausted.
    """
    delay = BASE_DELAY_SECONDS
    last_exception: Exception | None = None

    for attempt in range(MAX_RETRIES + 1):
        # Wait before request (always, to be respectful)
        if attempt > 0:
            # Add jitter to avoid thundering herd
            jitter = random.uniform(0, delay * 0.1)
            sleep_time = delay + jitter
            logger.info(f"Rate limited. Waiting {sleep_time:.1f}s (attempt {attempt + 1}/{MAX_RETRIES + 1})")
            time.sleep(sleep_time)
            delay = min(delay * BACKOFF_FACTOR, MAX_BACKOFF_SECONDS)
        else:
            time.sleep(BASE_DELAY_SECONDS)

        try:
            if params:
                response = client.get(url, params=params, follow_redirects=follow_redirects)
            else:
                response = client.get(url, follow_redirects=follow_redirects)

            # Handle rate limiting (429) and server errors (5xx)
            if response.status_code == 429:
                # Check for Retry-After header
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(float(retry_after), delay)
                    except ValueError:
                        pass
                last_exception = httpx.HTTPStatusError(
                    f"Rate limited (429)",
                    request=response.request,
                    response=response,
                )
                continue

            if response.status_code >= 500:
                last_exception = httpx.HTTPStatusError(
                    f"Server error ({response.status_code})",
                    request=response.request,
                    response=response,
                )
                continue

            # Raise for other client errors
            response.raise_for_status()
            return response

        except httpx.TimeoutException as e:
            last_exception = e
            logger.warning(f"Request timed out: {e}")
            continue
        except httpx.RequestError as e:
            last_exception = e
            logger.warning(f"Request failed: {e}")
            continue

    # All retries exhausted
    if last_exception:
        raise last_exception
    raise httpx.HTTPError("All retries exhausted")


def search_opinions(
    client: httpx.Client,
    query: str,
    max_results: int,
    *,
    court_filter: str | None = None,
    filed_after: str | None = None,
) -> list[dict[str, Any]]:
    """Search CourtListener for opinions matching a query.

    Uses cursor-based pagination and filters for opinions that have
    downloadable PDFs.

    Args:
        client: HTTP client for requests.
        query: Search query string.
        max_results: Maximum number of results to return.
        court_filter: Court ID to filter results (e.g., "cafc").
        filed_after: Only return opinions filed after this date (YYYY-MM-DD).

    Returns:
        List of opinion metadata dictionaries.
    """
    results: list[dict[str, Any]] = []
    params: dict[str, str | int] = {
        "q": query,
        "type": "o",  # opinions
        "order_by": "dateFiled desc",
        "page_size": 20,
    }
    if court_filter:
        params["court"] = court_filter
    if filed_after:
        params["filed_after"] = filed_after

    url: str | None = COURTLISTENER_SEARCH_URL
    use_params = True  # Only use params on first request

    with tqdm(total=max_results, desc="Searching", unit="opinions") as pbar:
        while url and len(results) < max_results:
            try:
                if use_params:
                    response = request_with_retry(client, url, params=params)
                    use_params = False
                else:
                    # Cursor-based pagination URL already has params
                    response = request_with_retry(client, url)

                data = response.json()
            except httpx.HTTPError as e:
                logger.error(f"Search request failed: {e}")
                break

            batch = data.get("results", [])
            if not batch:
                break

            # Filter to only opinions with downloadable PDFs
            for item in batch:
                if len(results) >= max_results:
                    break

                opinions = item.get("opinions", [])
                for opinion in opinions:
                    if len(results) >= max_results:
                        break

                    local_path = opinion.get("local_path")
                    if local_path and local_path.endswith(".pdf"):
                        results.append({
                            "cluster_id": item.get("cluster_id"),
                            "case_name": item.get("caseName"),
                            "court": item.get("court"),
                            "court_id": item.get("court_id"),
                            "date_filed": item.get("dateFiled"),
                            "docket_number": item.get("docketNumber"),
                            "citations": item.get("citation", []),
                            "opinion_id": opinion.get("id"),
                            "local_path": local_path,
                            "download_url": opinion.get("download_url"),
                            "opinion_type": opinion.get("type"),
                        })
                        pbar.update(1)

            url = data.get("next")

    return results


def download_pdf(client: httpx.Client, local_path: str, output_path: Path) -> bool:
    """Download a PDF from CourtListener storage.

    Args:
        client: HTTP client for requests.
        local_path: Path on CourtListener storage (e.g., "pdf/2025/03/10/file.pdf").
        output_path: Local path to save the file.

    Returns:
        True if download succeeded, False otherwise.
    """
    url = f"{COURTLISTENER_STORAGE_URL}/{local_path}"
    try:
        response = request_with_retry(client, url, follow_redirects=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return True
    except httpx.HTTPError as e:
        logger.warning(f"Failed to download {url}: {e}")
        return False


def download_corpus(
    query: str,
    corpus_name: str,
    data_dir: Path,
    max_docs: int,
    *,
    court_filter: str | None = None,
    filed_after: str | None = None,
) -> None:
    """Download a corpus of opinions based on a search query.

    Creates or updates a corpus directory with PDFs and metadata.
    Supports resumable downloads by checking existing files.

    Args:
        query: Search query string.
        corpus_name: Name for the corpus directory.
        data_dir: Base data directory.
        max_docs: Maximum number of documents to download.
        court_filter: Optional court ID filter.
        filed_after: Only download opinions filed after this date.
    """
    corpus_dir = data_dir / corpus_name
    opinions_dir = corpus_dir / "opinions"
    metadata_path = corpus_dir / "metadata.json"

    opinions_dir.mkdir(parents=True, exist_ok=True)

    # Load existing metadata for resume capability
    existing_metadata: dict[str, dict[str, Any]] = {}
    if metadata_path.exists():
        with metadata_path.open(encoding="utf-8") as f:
            existing_data = json.load(f)
            existing_metadata = {
                str(item["opinion_id"]): item
                for item in existing_data.get("opinions", [])
            }
        logger.info(f"Found {len(existing_metadata)} existing opinions in metadata")

    # Count existing PDFs
    existing_pdfs = set(p.stem for p in opinions_dir.glob("*.pdf"))
    logger.info(f"Found {len(existing_pdfs)} existing PDFs")

    headers = {
        "User-Agent": "BiteSizeRAG-Corpus-Builder/1.0 (legal research; rate-limited)",
    }

    with httpx.Client(headers=headers, timeout=60.0) as client:
        logger.info(f"Searching for opinions matching: {query}")

        opinions = search_opinions(
            client,
            query,
            max_results=max_docs,
            court_filter=court_filter,
            filed_after=filed_after,
        )

        logger.info(f"Found {len(opinions)} opinions with PDFs")

        # Download PDFs
        downloaded = 0
        skipped = 0
        failed = 0

        for opinion in tqdm(opinions, desc="Downloading PDFs", unit="files"):
            opinion_id = str(opinion["opinion_id"])
            pdf_filename = f"{opinion_id}.pdf"
            pdf_path = opinions_dir / pdf_filename

            # Skip if already downloaded
            if pdf_path.exists():
                skipped += 1
                # Ensure metadata is updated even for existing files
                if opinion_id not in existing_metadata:
                    existing_metadata[opinion_id] = opinion
                continue

            if download_pdf(client, opinion["local_path"], pdf_path):
                downloaded += 1
                existing_metadata[opinion_id] = opinion
            else:
                failed += 1
                logger.warning(f"Failed to download opinion {opinion_id}")

        # Save metadata
        metadata = {
            "corpus": corpus_name,
            "search_query": query,
            "court_filter": court_filter,
            "total_opinions": len(existing_metadata),
            "opinions": list(existing_metadata.values()),
        }

        with metadata_path.open("w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        logger.info(f"Downloaded: {downloaded}, Skipped: {skipped}, Failed: {failed}")
        logger.info(f"Total opinions in corpus: {len(existing_metadata)}")
        logger.info(f"Output directory: {corpus_dir}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download court opinions from CourtListener for RAG evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    uv run python download_opinions.py "patent infringement" --corpus patent_cases
    uv run python download_opinions.py "Clean Water Act" --corpus environmental --max-docs 200
    uv run python download_opinions.py "asylum" --corpus immigration --court cafc
        """,
    )
    parser.add_argument(
        "query",
        type=str,
        help="Search query for CourtListener (e.g., 'patent infringement')",
    )
    parser.add_argument(
        "--corpus",
        type=str,
        required=True,
        help="Name for the corpus directory (e.g., 'patent_cases')",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=150,
        help="Maximum documents to download (default: 150)",
    )
    parser.add_argument(
        "--court",
        type=str,
        default=None,
        help="Filter by court ID (e.g., 'cafc' for Federal Circuit)",
    )
    parser.add_argument(
        "--filed-after",
        type=str,
        default=None,
        help="Only download opinions filed after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Data directory path (default: ../data/)",
    )

    args = parser.parse_args()

    # Determine data directory
    script_dir = Path(__file__).resolve().parent
    data_dir = args.data_dir or (script_dir.parent / "data")
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        download_corpus(
            query=args.query,
            corpus_name=args.corpus,
            data_dir=data_dir,
            max_docs=args.max_docs,
            court_filter=args.court,
            filed_after=args.filed_after,
        )
        logger.info("Download complete!")

    except KeyboardInterrupt:
        logger.warning("\nDownload interrupted by user (Ctrl+C)")
        logger.info("Progress has been saved. Re-run to resume.")
        sys.exit(130)


if __name__ == "__main__":
    main()
