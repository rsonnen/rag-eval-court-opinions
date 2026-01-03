# rag-eval-court-opinions

Evaluation corpus of court opinions from CourtListener for testing RAG (Retrieval-Augmented Generation) systems.

## What This Is

This repository contains **evaluation data for RAG systems**:

- **corpus.yaml** - Evaluation configuration defining domain context and testing scenarios
- **Generated questions** - Validated Q/A pairs for evaluation (where available)
- **metadata.json** - Opinion inventory with CourtListener IDs
- **Download script** - Fetches PDFs from CourtListener storage

The actual PDF opinions are not included - they are public domain works hosted by CourtListener.

## Quick Start

Download opinions from a pre-curated corpus:

```bash
cd scripts
uv sync
uv run python download_opinions.py --corpus patent_law --data-dir ../data
```

## Purpose

Court opinions are a realistic use case for legal research assistants. This corpus tests:

- **Retrieval**: Precise clause lookup, citation navigation, legal reasoning chains
- **Document processing**: Long-form structured text with footnotes, citations, complex formatting
- **Query types**: "What precedent applies to X?", "How did the court reason about Y?", cross-case synthesis

## Usage

```bash
# Install dependencies
uv sync

# Download a corpus
uv run python download_opinions.py "patent infringement" --corpus patent_law --max-docs 150
uv run python download_opinions.py "Clean Water Act" --corpus environmental --max-docs 200
uv run python download_opinions.py "asylum deportation" --corpus immigration --max-docs 150

# Specify output directory
uv run python download_opinions.py "antitrust" --corpus antitrust --max-docs 100 --data-dir /path/to/data

# Filter by court
uv run python download_opinions.py "patent" --corpus patent_cafc --court cafc --max-docs 100

# Filter by date
uv run python download_opinions.py "First Amendment" --corpus first_amendment_recent --filed-after 2020-01-01
```

## Output Structure

```
data/<corpus>/
    corpus.yaml         # Evaluation configuration
    opinions/           # PDF files named by opinion ID (gitignored)
        12345.pdf
        12346.pdf
        ...
    metadata.json       # Opinion metadata for all downloaded documents

scripts/
    download_opinions.py  # Fetch opinions and build corpora
```

### Metadata Format

```json
{
  "corpus": "patent_law",
  "search_query": "patent infringement",
  "court_filter": null,
  "total_opinions": 150,
  "opinions": [
    {
      "cluster_id": 10763338,
      "case_name": "Example Corp v. Patent Holder LLC",
      "court": "Court of Appeals for the Federal Circuit",
      "court_id": "cafc",
      "date_filed": "2025-01-15",
      "docket_number": "24-1234",
      "citations": ["123 F.4th 456"],
      "opinion_id": 11229923,
      "local_path": "pdf/2025/01/15/example_v_patent_holder.pdf",
      "download_url": "https://...",
      "opinion_type": "combined-opinion"
    }
  ]
}
```

## Suggested Corpora

Based on the RAGAS evaluation TODO, create these topic corpora (100-500 docs each):

| Corpus | Search Query | Notes |
|--------|--------------|-------|
| patent_law | `"patent infringement"` | Consider `--court cafc` for Federal Circuit |
| environmental | `"Clean Water Act" OR "Clean Air Act" OR "EPA"` | EPA regulatory cases |
| first_amendment | `"First Amendment" "free speech"` | Constitutional law |
| contract_disputes | `"breach of contract"` | Commercial litigation |
| employment_discrimination | `"Title VII" "employment discrimination"` | Civil rights |
| antitrust | `"Sherman Act" OR "antitrust"` | Competition law |
| immigration | `"asylum" OR "deportation"` | Immigration proceedings |
| criminal_sentencing | `"sentencing guidelines"` | Criminal appeals |

## Features

- **Resumable downloads**: Re-run the same command to continue interrupted downloads
- **Rate limiting**: Conservative 3-second delays with exponential backoff on 429s
- **Metadata tracking**: All opinion metadata saved for downstream processing

## API Details

- **Search**: `GET https://www.courtlistener.com/api/rest/v4/search/?q=<query>&type=o`
- **PDFs**: `https://storage.courtlistener.com/<local_path>` (public, no auth)
- **Pagination**: Cursor-based via `next` URL in response

CourtListener is a nonprofit project of [Free Law Project](https://free.law/). Be respectful with rate limits.

## Licensing

**This repository** (scripts, configurations): MIT License

**Court opinions**: Public domain (government works not subject to copyright)

**CourtListener data**: [CC BY-NC](https://creativecommons.org/licenses/by-nc/4.0/) for non-commercial use. See [CourtListener Terms](https://www.courtlistener.com/terms/).

## Requirements

- Python 3.11+
- Dependencies: `httpx`, `tqdm` (see pyproject.toml)
