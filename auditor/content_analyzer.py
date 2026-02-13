"""Content analyzer using Claude API for article auditing."""

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from anthropic import Anthropic
from bs4 import BeautifulSoup


@dataclass
class Issue:
    """Represents a single audit issue."""
    category: str  # 'actionable', 'brief', 'targeted', 'technical', 'audience'
    severity: str  # 'critical', 'warning', 'suggestion'
    description: str
    location: Optional[str] = None  # Where in the article the issue occurs
    recommendation: Optional[str] = None


@dataclass
class AnalysisResult:
    """Results from content analysis."""
    overall_score: int  # 0-100
    audience_detected: str  # 'Buyer', 'Seller', 'Both'
    audience_mismatch: bool
    issues: list[Issue] = field(default_factory=list)
    has_web_instructions: bool = False
    has_app_instructions: bool = False
    hardcoded_links: list[str] = field(default_factory=list)
    member_services_flag: bool = False
    flag_reason: Optional[str] = None
    raw_analysis: Optional[str] = None


AUDIT_PROMPT = """You are an expert Help Center content auditor for Etsy's support documentation (help.etsy.com). Analyze the following article against Etsy's content standards.

## Audit Framework

### 1. Audience Detection & Mismatch
- Identify if article is for: Buyer, Seller, or Both
- Declared segment from URL: {declared_segment}
- Flag mismatches (e.g., buyer article with seller-only terms like "Shop Manager", "listing", "order fulfillment")
- Look for inappropriate cross-linking (buyer articles linking to seller tools or vice versa)

### 2. ABT Standard (Actionable, Brief, Targeted)

**Actionable:**
- Are steps complete and followable?
- Does it include BOTH web (Etsy.com) AND app (Etsy App) instructions where applicable?
- Are button names and navigation paths specific?

**Brief:**
- Is language concise?
- Flag: marketing jargon, legalese, unnecessary repetition, filler phrases
- Each sentence should add value

**Targeted:**
- Does title match user intent/search query?
- Is the most important information at the top?
- Is the scope appropriate (not too broad or narrow)?

### 3. Technical Hygiene
- Check for hardcoded language tags in links (e.g., /en-us/ should be removed for dynamic localization)
- Check for outdated UI references
- Verify internal links use relative paths where appropriate

## Article to Analyze

**Title:** {title}
**URL:** {url}
**Section:** {section}
**Declared Audience (from URL segment):** {declared_segment}

**Content:**
{content}

## Response Format

Respond with a JSON object containing:
```json
{{
  "overall_score": <0-100>,
  "audience_detected": "<Buyer|Seller|Both>",
  "audience_mismatch": <true|false>,
  "audience_mismatch_reason": "<explanation if mismatch>",
  "has_web_instructions": <true|false>,
  "has_app_instructions": <true|false>,
  "issues": [
    {{
      "category": "<actionable|brief|targeted|technical|audience>",
      "severity": "<critical|warning|suggestion>",
      "description": "<what's wrong>",
      "location": "<where in article, if specific>",
      "recommendation": "<how to fix>"
    }}
  ],
  "hardcoded_links": ["<list of links with hardcoded language tags>"],
  "member_services_flag": <true|false>,
  "flag_reason": "<why human verification needed, if flagged>",
  "summary": "<2-3 sentence overall assessment>"
}}
```

Be thorough but practical. Focus on issues that genuinely impact user experience."""


class ContentAnalyzer:
    """Analyzes article content using Claude API."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize the content analyzer.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
        """
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def _extract_text(self, html_content: str) -> str:
        """Extract readable text from HTML content."""
        soup = BeautifulSoup(html_content, "lxml")

        # Remove script and style elements
        for element in soup(["script", "style"]):
            element.decompose()

        # Get text with some structure preserved
        text = soup.get_text(separator="\n", strip=True)

        # Clean up excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text

    def _extract_links(self, html_content: str) -> list[dict]:
        """Extract all links from HTML content."""
        soup = BeautifulSoup(html_content, "lxml")
        links = []

        for a in soup.find_all("a", href=True):
            links.append({
                "text": a.get_text(strip=True),
                "href": a["href"]
            })

        return links

    def _check_hardcoded_links(self, html_content: str) -> list[str]:
        """Find links with hardcoded language tags."""
        soup = BeautifulSoup(html_content, "lxml")
        hardcoded = []

        # Pattern for hardcoded language tags in Etsy help URLs
        pattern = re.compile(r'/hc/[a-z]{2}-[a-z]{2}/')

        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "help.etsy.com" in href or href.startswith("/hc/"):
                if pattern.search(href):
                    hardcoded.append(href)

        return hardcoded

    def analyze(self, article) -> AnalysisResult:
        """
        Analyze an article for content quality issues.

        Args:
            article: Article object from ZendeskClient

        Returns:
            AnalysisResult with findings
        """
        # Extract text for analysis
        text_content = self._extract_text(article.body)

        # Pre-check hardcoded links
        hardcoded_links = self._check_hardcoded_links(article.body)

        # Build the prompt
        prompt = AUDIT_PROMPT.format(
            title=article.title,
            url=article.html_url,
            section=article.section_name or "Unknown",
            declared_segment=article.audience,
            content=text_content[:15000]  # Limit content length
        )

        # Call Claude
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Parse response
        response_text = response.content[0].text

        # Extract JSON from response
        try:
            # Try to find JSON in the response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")
        except (json.JSONDecodeError, ValueError):
            # Return a basic result if parsing fails
            return AnalysisResult(
                overall_score=0,
                audience_detected="Unknown",
                audience_mismatch=False,
                issues=[Issue(
                    category="technical",
                    severity="critical",
                    description="Failed to parse analysis response",
                    recommendation="Please try again"
                )],
                raw_analysis=response_text
            )

        # Build result
        issues = []
        for issue_data in analysis.get("issues", []):
            issues.append(Issue(
                category=issue_data.get("category", "technical"),
                severity=issue_data.get("severity", "warning"),
                description=issue_data.get("description", ""),
                location=issue_data.get("location"),
                recommendation=issue_data.get("recommendation")
            ))

        # Add hardcoded link issues if found (from our pre-check)
        all_hardcoded = list(set(hardcoded_links + analysis.get("hardcoded_links", [])))
        if all_hardcoded:
            issues.append(Issue(
                category="technical",
                severity="warning",
                description=f"Found {len(all_hardcoded)} link(s) with hardcoded language tags",
                recommendation="Remove /en-us/ or similar language tags from internal links for dynamic localization"
            ))

        return AnalysisResult(
            overall_score=analysis.get("overall_score", 0),
            audience_detected=analysis.get("audience_detected", "Unknown"),
            audience_mismatch=analysis.get("audience_mismatch", False),
            issues=issues,
            has_web_instructions=analysis.get("has_web_instructions", False),
            has_app_instructions=analysis.get("has_app_instructions", False),
            hardcoded_links=all_hardcoded,
            member_services_flag=analysis.get("member_services_flag", False),
            flag_reason=analysis.get("flag_reason"),
            raw_analysis=analysis.get("summary")
        )
