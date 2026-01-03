# rag-eval-court-opinions

Evaluation corpus of court opinions from CourtListener for testing RAG systems.

## What This Is

This repository contains **evaluation data for RAG systems**:

- **corpus.yaml** - Evaluation scenarios (in each corpus directory)
- **metadata.json** - Opinion inventory with CourtListener IDs
- **Generated questions** - Validated Q/A pairs (where available)

The actual PDF opinions are not included. Use `download_opinions.py` to fetch them from CourtListener.

## Quick Start

```bash
cd scripts
uv sync
uv run python download_opinions.py patent_law --max-docs 5
```

## Available Corpora

| Corpus | Opinions | Description |
|--------|----------|-------------|
| `patent_law` | 150 | Patent infringement and IP cases |
| `environmental` | 150 | Clean Water Act, Clean Air Act, EPA cases |
| `first_amendment` | 150 | First Amendment free speech cases |
| `antitrust` | 150 | Sherman Act and competition law |
| `immigration` | 150 | Asylum and deportation proceedings |

All corpora were built December 2025 from CourtListener's public archive.

## Directory Structure

```
data/<corpus>/
    corpus.yaml         # Evaluation configuration
    metadata.json       # Opinion inventory
    opinions/           # Downloaded PDFs (gitignored)

scripts/
    download_opinions.py  # Fetch opinions from existing metadata
    build_corpus.py       # Build new corpora via CourtListener search
```

## Metadata Format

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

## Downloading Opinions

The download script fetches PDFs from CourtListener storage based on existing metadata:

```bash
cd scripts
uv run python download_opinions.py patent_law --max-docs 5
uv run python download_opinions.py environmental
```

| Option | Description |
|--------|-------------|
| `corpus` | Corpus name (e.g., patent_law) |
| `--max-docs` | Maximum documents to download (default: all) |
| `--delay` | Delay between requests in seconds (default: 1.0) |

## Building New Corpora

The build script searches CourtListener and creates new corpora:

```bash
cd scripts
uv run python build_corpus.py "patent infringement" --corpus patent_law --max-docs 150
uv run python build_corpus.py "Clean Water Act" --corpus environmental --max-docs 200
```

| Option | Description |
|--------|-------------|
| `query` | Search query for CourtListener (required) |
| `--corpus` | Corpus directory name (required) |
| `--max-docs` | Maximum documents to download (default: 150) |
| `--court` | Filter by court ID (e.g., 'cafc' for Federal Circuit) |
| `--filed-after` | Only download opinions filed after date (YYYY-MM-DD) |
| `--data-dir` | Output directory (default: ../data/) |

### Rate Limiting

Both scripts respect CourtListener (a small nonprofit) with delays between requests.

### Evaluation Configuration

Each corpus contains a `corpus.yaml` with evaluation scenarios:

```yaml
# data/patent_law/corpus.yaml
name: "Patent Law Court Opinions"

corpus_context: >
  150 patent law court opinions from CourtListener, dated May-December 2025...

scenarios:
  graduate_exam:
    name: "Graduate Patent Law Final"
    description: >
      Questions testing understanding of court's legal reasoning,
      controlling legal standards, and how facts determined outcomes...

  paralegal_research:
    name: "Paralegal Research Skills"
    description: >
      Questions testing ability to locate specific holdings,
      identify procedural posture, extract key facts...

  rag_eval:
    name: "RAG System Evaluation"
    description: >
      Questions with specific, verifiable answers requiring the
      actual document - particular quotes, specific factual details...
```

## Licensing

**This repository**: MIT License

**Court opinions**: Public domain (government works not subject to copyright)

**CourtListener data**: [CC BY-NC](https://creativecommons.org/licenses/by-nc/4.0/) for non-commercial use. See [CourtListener Terms](https://www.courtlistener.com/terms/).
