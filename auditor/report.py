"""Audit report generation and formatting."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json

from .content_analyzer import AnalysisResult, Issue
from .ui_verifier import UIVerificationReport
from .zendesk_client import Article


@dataclass
class AuditReport:
    """Complete audit report for a Help Center article."""
    article_id: int
    article_title: str
    article_url: str
    audit_timestamp: str

    # Overall assessment
    overall_score: int  # 0-100
    quality_rating: str  # 'Excellent', 'Good', 'Needs Work', 'Critical Issues'

    # Audience
    declared_audience: str
    detected_audience: str
    audience_mismatch: bool

    # Content completeness
    has_web_instructions: bool
    has_app_instructions: bool

    # Issues by category
    actionable_issues: list[Issue] = field(default_factory=list)
    brief_issues: list[Issue] = field(default_factory=list)
    targeted_issues: list[Issue] = field(default_factory=list)
    technical_issues: list[Issue] = field(default_factory=list)
    audience_issues: list[Issue] = field(default_factory=list)

    # Technical details
    hardcoded_links: list[str] = field(default_factory=list)

    # UI verification
    ui_elements_verified: int = 0
    ui_elements_total: int = 0
    ui_confidence: float = 0.0
    ui_manual_review_items: list[str] = field(default_factory=list)

    # Flags
    member_services_flag: bool = False
    flag_reason: Optional[str] = None

    # Summary
    summary: Optional[str] = None

    @property
    def total_issues(self) -> int:
        return (
            len(self.actionable_issues) +
            len(self.brief_issues) +
            len(self.targeted_issues) +
            len(self.technical_issues) +
            len(self.audience_issues)
        )

    @property
    def critical_issues(self) -> list[Issue]:
        all_issues = (
            self.actionable_issues +
            self.brief_issues +
            self.targeted_issues +
            self.technical_issues +
            self.audience_issues
        )
        return [i for i in all_issues if i.severity == "critical"]

    @property
    def warnings(self) -> list[Issue]:
        all_issues = (
            self.actionable_issues +
            self.brief_issues +
            self.targeted_issues +
            self.technical_issues +
            self.audience_issues
        )
        return [i for i in all_issues if i.severity == "warning"]

    @property
    def suggestions(self) -> list[Issue]:
        all_issues = (
            self.actionable_issues +
            self.brief_issues +
            self.targeted_issues +
            self.technical_issues +
            self.audience_issues
        )
        return [i for i in all_issues if i.severity == "suggestion"]

    def to_dict(self) -> dict:
        """Convert report to dictionary for serialization."""
        return {
            "article_id": self.article_id,
            "article_title": self.article_title,
            "article_url": self.article_url,
            "audit_timestamp": self.audit_timestamp,
            "overall_score": self.overall_score,
            "quality_rating": self.quality_rating,
            "declared_audience": self.declared_audience,
            "detected_audience": self.detected_audience,
            "audience_mismatch": self.audience_mismatch,
            "has_web_instructions": self.has_web_instructions,
            "has_app_instructions": self.has_app_instructions,
            "total_issues": self.total_issues,
            "critical_count": len(self.critical_issues),
            "warning_count": len(self.warnings),
            "suggestion_count": len(self.suggestions),
            "issues": {
                "actionable": [_issue_to_dict(i) for i in self.actionable_issues],
                "brief": [_issue_to_dict(i) for i in self.brief_issues],
                "targeted": [_issue_to_dict(i) for i in self.targeted_issues],
                "technical": [_issue_to_dict(i) for i in self.technical_issues],
                "audience": [_issue_to_dict(i) for i in self.audience_issues],
            },
            "hardcoded_links": self.hardcoded_links,
            "ui_verification": {
                "elements_verified": self.ui_elements_verified,
                "elements_total": self.ui_elements_total,
                "confidence": self.ui_confidence,
                "manual_review_items": self.ui_manual_review_items,
            },
            "member_services_flag": self.member_services_flag,
            "flag_reason": self.flag_reason,
            "summary": self.summary,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Convert report to Markdown format."""
        lines = []

        # Header
        lines.append(f"# Audit Report: {self.article_title}")
        lines.append("")
        lines.append(f"**Article ID:** {self.article_id}")
        lines.append(f"**URL:** {self.article_url}")
        lines.append(f"**Audit Date:** {self.audit_timestamp}")
        lines.append("")

        # Overall assessment
        lines.append("## Overall Assessment")
        lines.append("")
        score_emoji = "🟢" if self.overall_score >= 80 else "🟡" if self.overall_score >= 60 else "🔴"
        lines.append(f"**Score:** {score_emoji} {self.overall_score}/100 ({self.quality_rating})")
        lines.append("")

        if self.summary:
            lines.append(f"_{self.summary}_")
            lines.append("")

        # Audience
        lines.append("## Audience")
        lines.append("")
        mismatch_indicator = "⚠️ MISMATCH" if self.audience_mismatch else "✓"
        lines.append(f"- **Declared:** {self.declared_audience}")
        lines.append(f"- **Detected:** {self.detected_audience} {mismatch_indicator}")
        lines.append("")

        # Content completeness
        lines.append("## Content Completeness")
        lines.append("")
        web_check = "✓" if self.has_web_instructions else "✗"
        app_check = "✓" if self.has_app_instructions else "✗"
        lines.append(f"- Web instructions: {web_check}")
        lines.append(f"- App instructions: {app_check}")
        lines.append("")

        # Issues summary
        lines.append("## Issues Summary")
        lines.append("")
        lines.append(f"- 🔴 Critical: {len(self.critical_issues)}")
        lines.append(f"- 🟡 Warnings: {len(self.warnings)}")
        lines.append(f"- 🔵 Suggestions: {len(self.suggestions)}")
        lines.append("")

        # Detailed issues by category
        if self.actionable_issues:
            lines.append("### Actionable Issues")
            lines.append("")
            for issue in self.actionable_issues:
                lines.append(_format_issue_md(issue))
            lines.append("")

        if self.brief_issues:
            lines.append("### Brief Issues")
            lines.append("")
            for issue in self.brief_issues:
                lines.append(_format_issue_md(issue))
            lines.append("")

        if self.targeted_issues:
            lines.append("### Targeted Issues")
            lines.append("")
            for issue in self.targeted_issues:
                lines.append(_format_issue_md(issue))
            lines.append("")

        if self.technical_issues:
            lines.append("### Technical Issues")
            lines.append("")
            for issue in self.technical_issues:
                lines.append(_format_issue_md(issue))
            lines.append("")

        if self.audience_issues:
            lines.append("### Audience Issues")
            lines.append("")
            for issue in self.audience_issues:
                lines.append(_format_issue_md(issue))
            lines.append("")

        # Hardcoded links
        if self.hardcoded_links:
            lines.append("## Hardcoded Links (Need Dynamic Localization)")
            lines.append("")
            for link in self.hardcoded_links:
                lines.append(f"- `{link}`")
            lines.append("")

        # UI Verification
        if self.ui_elements_total > 0:
            lines.append("## UI Verification")
            lines.append("")
            lines.append(f"- Elements found: {self.ui_elements_total}")
            lines.append(f"- Confidence: {self.ui_confidence:.0%}")
            lines.append("")
            if self.ui_manual_review_items:
                lines.append("**Items requiring manual review:**")
                for item in self.ui_manual_review_items:
                    lines.append(f"- {item}")
                lines.append("")

        # Member Services Flag
        if self.member_services_flag:
            lines.append("## ⚠️ Member Services Flag")
            lines.append("")
            lines.append("**This article requires human verification.**")
            if self.flag_reason:
                lines.append(f"Reason: {self.flag_reason}")
            lines.append("")

        return "\n".join(lines)


def _issue_to_dict(issue: Issue) -> dict:
    """Convert Issue to dictionary."""
    return {
        "severity": issue.severity,
        "description": issue.description,
        "location": issue.location,
        "recommendation": issue.recommendation,
    }


def _format_issue_md(issue: Issue) -> str:
    """Format a single issue for Markdown output."""
    severity_icon = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}.get(issue.severity, "⚪")
    lines = [f"- {severity_icon} **{issue.description}**"]
    if issue.location:
        lines.append(f"  - Location: {issue.location}")
    if issue.recommendation:
        lines.append(f"  - Recommendation: {issue.recommendation}")
    return "\n".join(lines)


def _get_quality_rating(score: int) -> str:
    """Convert numeric score to quality rating."""
    if score >= 90:
        return "Excellent"
    elif score >= 75:
        return "Good"
    elif score >= 60:
        return "Needs Work"
    else:
        return "Critical Issues"


def generate_report(
    article: Article,
    analysis: AnalysisResult,
    ui_report: Optional[UIVerificationReport] = None
) -> AuditReport:
    """
    Generate a complete audit report from analysis results.

    Args:
        article: The article that was audited
        analysis: Content analysis results
        ui_report: Optional UI verification results

    Returns:
        Complete AuditReport
    """
    # Categorize issues
    actionable_issues = [i for i in analysis.issues if i.category == "actionable"]
    brief_issues = [i for i in analysis.issues if i.category == "brief"]
    targeted_issues = [i for i in analysis.issues if i.category == "targeted"]
    technical_issues = [i for i in analysis.issues if i.category == "technical"]
    audience_issues = [i for i in analysis.issues if i.category == "audience"]

    # UI verification stats
    ui_elements_verified = 0
    ui_elements_total = 0
    ui_confidence = 1.0
    ui_manual_items = []

    if ui_report:
        ui_elements_total = len(ui_report.elements_found)
        ui_elements_verified = len([r for r in ui_report.results if r.status == "verified"])
        ui_confidence = ui_report.overall_confidence
        ui_manual_items = ui_report.manual_review_items

    return AuditReport(
        article_id=article.id,
        article_title=article.title,
        article_url=article.html_url,
        audit_timestamp=datetime.now().isoformat(),
        overall_score=analysis.overall_score,
        quality_rating=_get_quality_rating(analysis.overall_score),
        declared_audience=article.audience,
        detected_audience=analysis.audience_detected,
        audience_mismatch=analysis.audience_mismatch,
        has_web_instructions=analysis.has_web_instructions,
        has_app_instructions=analysis.has_app_instructions,
        actionable_issues=actionable_issues,
        brief_issues=brief_issues,
        targeted_issues=targeted_issues,
        technical_issues=technical_issues,
        audience_issues=audience_issues,
        hardcoded_links=analysis.hardcoded_links,
        ui_elements_verified=ui_elements_verified,
        ui_elements_total=ui_elements_total,
        ui_confidence=ui_confidence,
        ui_manual_review_items=ui_manual_items,
        member_services_flag=analysis.member_services_flag,
        flag_reason=analysis.flag_reason,
        summary=analysis.raw_analysis,
    )
