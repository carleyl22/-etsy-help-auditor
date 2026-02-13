"""Live UI verification for Etsy platform."""

import re
from dataclasses import dataclass, field
from typing import Optional
import requests
from bs4 import BeautifulSoup


@dataclass
class UIElement:
    """Represents a UI element or navigation path mentioned in an article."""
    text: str
    element_type: str  # 'button', 'navigation', 'menu', 'link', 'tab'
    context: str  # Surrounding text for context
    platform: str  # 'web', 'app', 'both', 'unknown'


@dataclass
class VerificationResult:
    """Result of UI verification."""
    element: UIElement
    status: str  # 'verified', 'unverified', 'potentially_outdated', 'error'
    confidence: float  # 0.0 to 1.0
    notes: Optional[str] = None
    source: Optional[str] = None  # Where we verified this


@dataclass
class UIVerificationReport:
    """Complete UI verification report for an article."""
    elements_found: list[UIElement] = field(default_factory=list)
    results: list[VerificationResult] = field(default_factory=list)
    overall_confidence: float = 0.0
    needs_manual_review: bool = False
    manual_review_items: list[str] = field(default_factory=list)


# Known Etsy UI patterns and their current status
# This acts as a baseline reference - can be updated as Etsy UI changes
KNOWN_UI_ELEMENTS = {
    # Shop Manager navigation
    "shop manager": {"status": "current", "platform": "web", "type": "navigation"},
    "listings": {"status": "current", "platform": "both", "type": "navigation"},
    "orders & shipping": {"status": "current", "platform": "web", "type": "navigation"},
    "messages": {"status": "current", "platform": "both", "type": "navigation"},
    "marketing": {"status": "current", "platform": "web", "type": "navigation"},
    "finances": {"status": "current", "platform": "web", "type": "navigation"},
    "settings": {"status": "current", "platform": "both", "type": "navigation"},
    "stats": {"status": "current", "platform": "both", "type": "navigation"},

    # Common buttons
    "add a listing": {"status": "current", "platform": "both", "type": "button"},
    "save": {"status": "current", "platform": "both", "type": "button"},
    "publish": {"status": "current", "platform": "both", "type": "button"},
    "edit": {"status": "current", "platform": "both", "type": "button"},
    "delete": {"status": "current", "platform": "both", "type": "button"},
    "renew": {"status": "current", "platform": "both", "type": "button"},
    "deactivate": {"status": "current", "platform": "both", "type": "button"},

    # Buyer-side navigation
    "your account": {"status": "current", "platform": "web", "type": "navigation"},
    "purchases and reviews": {"status": "current", "platform": "web", "type": "navigation"},
    "account settings": {"status": "current", "platform": "web", "type": "navigation"},
    "favorites": {"status": "current", "platform": "both", "type": "navigation"},
    "cart": {"status": "current", "platform": "both", "type": "navigation"},

    # App-specific
    "you tab": {"status": "current", "platform": "app", "type": "navigation"},
    "shop icon": {"status": "current", "platform": "app", "type": "navigation"},
    "three dots menu": {"status": "current", "platform": "app", "type": "menu"},
    "hamburger menu": {"status": "current", "platform": "app", "type": "menu"},
}

# Patterns that often indicate outdated UI
OUTDATED_PATTERNS = [
    r"click the gear icon",  # Replaced with different settings access
    r"go to your shop",  # Now "Shop Manager"
    r"direct checkout",  # Old feature name
    r"alchemy",  # Old search feature
]


class UIVerifier:
    """Verifies UI elements mentioned in articles against live Etsy site."""

    def __init__(self):
        """Initialize the UI verifier."""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; HelpCenterAuditor/1.0)"
        })

    def _extract_ui_elements(self, html_content: str) -> list[UIElement]:
        """Extract UI elements and navigation paths from article content."""
        soup = BeautifulSoup(html_content, "lxml")
        text = soup.get_text(separator=" ", strip=True)

        elements = []

        # Pattern for navigation paths: "Go to X > Y > Z" or "Select X > Y"
        nav_patterns = [
            r'(?:go to|navigate to|select|click|tap|open)\s+([A-Z][^.!?\n]{5,50}(?:\s*>\s*[A-Z][^.!?\n>]{2,30})*)',
            r'(?:from|in|under)\s+(?:the\s+)?([A-Z][^.!?\n]{3,30}(?:\s*>\s*[A-Z][^.!?\n>]{2,30})+)',
        ]

        for pattern in nav_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                path = match.group(1).strip()
                # Get surrounding context
                start = max(0, match.start() - 50)
                end = min(len(text), match.end() + 50)
                context = text[start:end]

                # Determine platform
                platform = "unknown"
                context_lower = context.lower()
                if "app" in context_lower or "mobile" in context_lower:
                    platform = "app"
                elif "website" in context_lower or "browser" in context_lower or "etsy.com" in context_lower:
                    platform = "web"

                elements.append(UIElement(
                    text=path,
                    element_type="navigation",
                    context=context,
                    platform=platform
                ))

        # Pattern for button names in quotes or bold
        button_patterns = [
            r'(?:click|tap|select|press)\s+(?:the\s+)?["\u201c]([^"\u201d]+)["\u201d]',
            r'(?:click|tap|select|press)\s+(?:the\s+)?<(?:strong|b)>([^<]+)</(?:strong|b)>',
            r'(?:click|tap|select|press)\s+(?:the\s+)?\*\*([^*]+)\*\*',
        ]

        for pattern in button_patterns:
            for match in re.finditer(pattern, html_content, re.IGNORECASE):
                button_text = match.group(1).strip()
                if len(button_text) > 2 and len(button_text) < 50:
                    start = max(0, match.start() - 50)
                    end = min(len(html_content), match.end() + 50)

                    elements.append(UIElement(
                        text=button_text,
                        element_type="button",
                        context=html_content[start:end],
                        platform="unknown"
                    ))

        return elements

    def _check_known_element(self, element: UIElement) -> Optional[VerificationResult]:
        """Check element against known UI elements database."""
        element_lower = element.text.lower().strip()

        # Direct match
        if element_lower in KNOWN_UI_ELEMENTS:
            info = KNOWN_UI_ELEMENTS[element_lower]
            return VerificationResult(
                element=element,
                status="verified" if info["status"] == "current" else "potentially_outdated",
                confidence=0.9,
                notes=f"Matched known UI element ({info['platform']})",
                source="known_elements_db"
            )

        # Check for outdated patterns
        for pattern in OUTDATED_PATTERNS:
            if re.search(pattern, element_lower):
                return VerificationResult(
                    element=element,
                    status="potentially_outdated",
                    confidence=0.7,
                    notes=f"Matches potentially outdated pattern: {pattern}",
                    source="outdated_patterns_db"
                )

        # Partial matches in navigation paths
        for known, info in KNOWN_UI_ELEMENTS.items():
            if known in element_lower or element_lower in known:
                return VerificationResult(
                    element=element,
                    status="verified",
                    confidence=0.7,
                    notes=f"Partial match to known element: {known}",
                    source="known_elements_db"
                )

        return None

    def _verify_live(self, element: UIElement) -> VerificationResult:
        """
        Attempt live verification of a UI element.

        Note: This is limited since we can't access authenticated Etsy pages.
        We can check public pages and documentation.
        """
        # For now, mark as needing manual review if we can't verify
        return VerificationResult(
            element=element,
            status="unverified",
            confidence=0.3,
            notes="Could not verify against known elements - manual review recommended",
            source="live_check"
        )

    def verify_article(self, html_content: str) -> UIVerificationReport:
        """
        Verify all UI elements in an article.

        Args:
            html_content: Article HTML body

        Returns:
            UIVerificationReport with all findings
        """
        elements = self._extract_ui_elements(html_content)
        results = []
        manual_review_items = []

        for element in elements:
            # First try known elements
            result = self._check_known_element(element)

            if result is None:
                # Try live verification
                result = self._verify_live(element)

            results.append(result)

            # Track items needing manual review
            if result.status in ["unverified", "potentially_outdated"]:
                manual_review_items.append(
                    f"{element.element_type.title()}: '{element.text}' - {result.notes}"
                )

        # Calculate overall confidence
        if results:
            overall_confidence = sum(r.confidence for r in results) / len(results)
        else:
            overall_confidence = 1.0  # No UI elements to verify

        return UIVerificationReport(
            elements_found=elements,
            results=results,
            overall_confidence=overall_confidence,
            needs_manual_review=len(manual_review_items) > 0,
            manual_review_items=manual_review_items
        )

    def fetch_etsy_page(self, url: str) -> Optional[str]:
        """
        Fetch a public Etsy page for verification.

        Args:
            url: URL to fetch

        Returns:
            Page HTML or None if failed
        """
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception:
            return None
