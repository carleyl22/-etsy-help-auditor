"""Zendesk Help Center API client for fetching articles."""

import re
from dataclasses import dataclass
from typing import Optional
import requests


@dataclass
class Article:
    """Represents a Zendesk Help Center article."""
    id: int
    title: str
    body: str
    html_url: str
    section_id: int
    section_name: Optional[str] = None
    locale: str = "en-us"
    segment: Optional[str] = None  # 'shopping', 'selling', or None

    @property
    def audience(self) -> str:
        """Determine audience based on segment parameter."""
        if self.segment == "shopping":
            return "Buyer"
        elif self.segment == "selling":
            return "Seller"
        return "Both/Unknown"


class ZendeskClient:
    """Client for interacting with Zendesk Help Center API."""

    def __init__(self, subdomain: str, email: str, api_token: str):
        """
        Initialize the Zendesk client.

        Args:
            subdomain: Zendesk subdomain (e.g., 'etsy' for etsy.zendesk.com)
            email: Email address for authentication
            api_token: Zendesk API token
        """
        self.subdomain = subdomain
        self.base_url = f"https://{subdomain}.zendesk.com/api/v2/help_center"
        self.auth = (f"{email}/token", api_token)
        self.session = requests.Session()
        self.session.auth = self.auth
        self.session.headers.update({
            "Content-Type": "application/json",
        })

    def _extract_article_id(self, url_or_id: str) -> int:
        """Extract article ID from URL or return the ID if already numeric."""
        if url_or_id.isdigit():
            return int(url_or_id)

        # Match patterns like /articles/123456 or /articles/123456-article-title
        match = re.search(r'/articles/(\d+)', url_or_id)
        if match:
            return int(match.group(1))

        raise ValueError(f"Could not extract article ID from: {url_or_id}")

    def _extract_segment(self, url: str) -> Optional[str]:
        """Extract segment parameter from URL."""
        match = re.search(r'[?&]segment=(\w+)', url)
        if match:
            return match.group(1)
        return None

    def get_article(self, url_or_id: str, locale: str = "en-us") -> Article:
        """
        Fetch a single article by URL or ID.

        Args:
            url_or_id: Article URL or numeric ID
            locale: Locale for the article (default: en-us)

        Returns:
            Article object with full content
        """
        article_id = self._extract_article_id(url_or_id)
        segment = self._extract_segment(url_or_id) if not url_or_id.isdigit() else None

        url = f"{self.base_url}/{locale}/articles/{article_id}"
        response = self.session.get(url)
        response.raise_for_status()

        data = response.json()["article"]

        # Get section name
        section_name = None
        if data.get("section_id"):
            try:
                section_name = self._get_section_name(data["section_id"], locale)
            except Exception:
                pass

        return Article(
            id=data["id"],
            title=data["title"],
            body=data["body"],
            html_url=data["html_url"],
            section_id=data["section_id"],
            section_name=section_name,
            locale=locale,
            segment=segment,
        )

    def _get_section_name(self, section_id: int, locale: str = "en-us") -> str:
        """Get the name of a section by ID."""
        url = f"{self.base_url}/{locale}/sections/{section_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()["section"]["name"]

    def list_articles(self, locale: str = "en-us", per_page: int = 30) -> list[Article]:
        """
        List all articles in the Help Center.

        Args:
            locale: Locale for articles
            per_page: Number of articles per page

        Returns:
            List of Article objects (without full body content initially)
        """
        articles = []
        url = f"{self.base_url}/{locale}/articles"
        params = {"per_page": per_page}

        while url:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for article_data in data["articles"]:
                articles.append(Article(
                    id=article_data["id"],
                    title=article_data["title"],
                    body=article_data["body"],
                    html_url=article_data["html_url"],
                    section_id=article_data["section_id"],
                    locale=locale,
                ))

            url = data.get("next_page")
            params = {}  # Clear params for pagination

        return articles

    def search_articles(self, query: str, locale: str = "en-us") -> list[Article]:
        """
        Search for articles matching a query.

        Args:
            query: Search query string
            locale: Locale for articles

        Returns:
            List of matching Article objects
        """
        url = f"{self.base_url}/articles/search"
        params = {"query": query, "locale": locale}

        response = self.session.get(url, params=params)
        response.raise_for_status()

        articles = []
        for result in response.json()["results"]:
            articles.append(Article(
                id=result["id"],
                title=result["title"],
                body=result.get("body", ""),
                html_url=result["html_url"],
                section_id=result.get("section_id", 0),
                locale=locale,
            ))

        return articles

    def test_connection(self) -> bool:
        """Test if the API credentials are valid."""
        try:
            url = f"{self.base_url}/en-us/articles"
            response = self.session.get(url, params={"per_page": 1})
            response.raise_for_status()
            return True
        except Exception:
            return False
