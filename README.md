# Etsy Help Center Auditor

A tool to audit Etsy Help Center articles (help.etsy.com) for content quality, technical accuracy, and alignment with Etsy's "Actionable, Brief, Targeted" content standards.

## Features

- **Single Article Audit** - Audit individual articles by URL or ID
- **Batch Audit** - Audit multiple articles at once
- **Search & Audit** - Search articles and audit from results
- **ABT Framework Analysis** - Checks Actionable, Brief, and Targeted standards
- **Audience Detection** - Identifies buyer vs seller content mismatches
- **Technical Hygiene** - Finds hardcoded language links, outdated UI references
- **Live UI Verification** - Verifies button names and navigation paths
- **Export Reports** - Download as Markdown or JSON

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with:
- `ZENDESK_EMAIL` - Your Etsy Zendesk email
- `ZENDESK_API_TOKEN` - Your Zendesk API token
- `ANTHROPIC_API_KEY` - Your Anthropic API key (for Claude)

### 3. Run the App

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

## Using the App

### Connect

1. Enter your credentials in the sidebar (or they'll auto-fill from `.env`)
2. Click "Connect" to establish API connections

### Single Article Audit

1. Go to "Single Article Audit" tab
2. Paste an article URL like `https://help.etsy.com/hc/en-us/articles/123456789?segment=selling`
3. Click "Audit Article"
4. Review the score card and detailed findings
5. Download report as Markdown or JSON

### Batch Audit

1. Go to "Batch Audit" tab
2. Enter multiple URLs or IDs (one per line)
3. Click "Audit All"
4. Review summary table and download combined report

### Search & Audit

1. Go to "Search Articles" tab
2. Enter a search query
3. Click on any result to audit it

## Audit Framework

### Audience Detection
- Identifies Buyer, Seller, or Both audiences
- Detects mismatches between URL segment and content

### ABT Standard

| Criterion | What it checks |
|-----------|----------------|
| **Actionable** | Complete steps, web + app instructions, specific button names |
| **Brief** | Concise language, no jargon or filler |
| **Targeted** | Title matches intent, important info at top |

### Technical Hygiene
- Hardcoded language tags (`/en-us/` in links)
- Outdated UI references
- Broken internal links

### UI Verification
- Extracts navigation paths and button names
- Verifies against known Etsy UI elements
- Flags items needing manual review

## Report Fields

- **Overall Score** - 0-100 quality rating
- **Quality Rating** - Excellent/Good/Needs Work/Critical
- **Issues by Category** - Actionable, Brief, Targeted, Technical, Audience
- **Member Services Flag** - Indicates need for human verification

## For Teammates

You don't need to set up the whole environment. You can:

1. Ask the admin for the shared `.env` file
2. Run `pip install -r requirements.txt`
3. Run `streamlit run app.py`
4. The app will be available in your browser

## Project Structure

```
claude-audit/
├── app.py              # Streamlit web interface
├── auditor/
│   ├── __init__.py
│   ├── zendesk_client.py   # Zendesk API integration
│   ├── content_analyzer.py # Claude-powered analysis
│   ├── ui_verifier.py      # Live UI verification
│   └── report.py           # Report generation
├── requirements.txt
├── .env.example
└── README.md
```

## Troubleshooting

**"Failed to connect to Zendesk"**
- Check your email and API token
- Ensure your Zendesk account has API access enabled

**"Analysis failed"**
- Check your Anthropic API key
- Ensure you have API credits available

**"UI verification failed"**
- This is non-critical; content analysis still works
- UI verification requires network access to Etsy
