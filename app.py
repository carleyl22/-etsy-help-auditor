"""
Etsy Help Center Auditor - Streamlit Web Application

A tool to audit Etsy Help Center articles for content quality,
technical accuracy, and alignment with Etsy's content standards.
"""

import os
import streamlit as st

from auditor import (
    ZendeskClient,
    ContentAnalyzer,
    UIVerifier,
    generate_report,
)


def get_secret(key: str, default: str = "") -> str:
    """Get secret from Streamlit secrets or environment variable."""
    # Try Streamlit secrets first (for cloud deployment)
    try:
        return st.secrets.get(key, "")
    except Exception:
        pass
    # Fall back to environment variable (for local development)
    return os.getenv(key, default)

# Page config
st.set_page_config(
    page_title="Etsy Help Center Auditor",
    page_icon="📝",
    layout="wide",
)

# Custom CSS
st.markdown("""
<style>
    .score-excellent { color: #28a745; font-size: 2em; font-weight: bold; }
    .score-good { color: #5cb85c; font-size: 2em; font-weight: bold; }
    .score-needswork { color: #f0ad4e; font-size: 2em; font-weight: bold; }
    .score-critical { color: #d9534f; font-size: 2em; font-weight: bold; }
    .issue-critical { background-color: #f8d7da; padding: 10px; border-radius: 5px; margin: 5px 0; }
    .issue-warning { background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 5px 0; }
    .issue-suggestion { background-color: #d1ecf1; padding: 10px; border-radius: 5px; margin: 5px 0; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "zendesk_client" not in st.session_state:
        st.session_state.zendesk_client = None
    if "analyzer" not in st.session_state:
        st.session_state.analyzer = None
    if "ui_verifier" not in st.session_state:
        st.session_state.ui_verifier = UIVerifier()
    if "audit_history" not in st.session_state:
        st.session_state.audit_history = []
    if "connected" not in st.session_state:
        st.session_state.connected = False


def connect_services():
    """Connect to Zendesk and Anthropic APIs."""
    with st.sidebar:
        st.header("🔐 Configuration")

        # Try to load from secrets/environment
        zendesk_email = get_secret("ZENDESK_EMAIL")
        zendesk_token = get_secret("ZENDESK_API_TOKEN")
        anthropic_key = get_secret("ANTHROPIC_API_KEY")

        # Input fields (pre-filled if env vars exist)
        zendesk_email = st.text_input(
            "Zendesk Email",
            value=zendesk_email,
            help="Your Zendesk email address"
        )
        zendesk_token = st.text_input(
            "Zendesk API Token",
            value=zendesk_token,
            type="password",
            help="Your Zendesk API token"
        )
        anthropic_key = st.text_input(
            "Anthropic API Key",
            value=anthropic_key,
            type="password",
            help="Your Anthropic API key for Claude"
        )

        if st.button("Connect", type="primary"):
            with st.spinner("Connecting..."):
                try:
                    # Initialize Zendesk client
                    client = ZendeskClient(
                        subdomain="etsy",
                        email=zendesk_email,
                        api_token=zendesk_token
                    )

                    # Test connection
                    if not client.test_connection():
                        st.error("Failed to connect to Zendesk. Check your credentials.")
                        return

                    # Initialize analyzer
                    analyzer = ContentAnalyzer(api_key=anthropic_key)

                    # Store in session
                    st.session_state.zendesk_client = client
                    st.session_state.analyzer = analyzer
                    st.session_state.connected = True

                    st.success("Connected successfully!")

                except Exception as e:
                    st.error(f"Connection error: {str(e)}")

        # Connection status
        if st.session_state.connected:
            st.success("✓ Connected to Zendesk & Claude")
        else:
            st.warning("Not connected")

        st.divider()

        # Audit history
        if st.session_state.audit_history:
            st.header("📋 Recent Audits")
            for i, audit in enumerate(reversed(st.session_state.audit_history[-5:])):
                with st.expander(f"{audit['title'][:30]}...", expanded=False):
                    st.write(f"Score: {audit['score']}/100")
                    st.write(f"Issues: {audit['issues']}")


def render_score_card(report):
    """Render the overall score card."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        score_class = (
            "score-excellent" if report.overall_score >= 90
            else "score-good" if report.overall_score >= 75
            else "score-needswork" if report.overall_score >= 60
            else "score-critical"
        )
        st.markdown(f"<div class='{score_class}'>{report.overall_score}/100</div>", unsafe_allow_html=True)
        st.caption(report.quality_rating)

    with col2:
        st.metric("Critical Issues", len(report.critical_issues))

    with col3:
        st.metric("Warnings", len(report.warnings))

    with col4:
        st.metric("Suggestions", len(report.suggestions))


def render_issues(issues, category_name):
    """Render issues for a category."""
    if not issues:
        st.success(f"No {category_name.lower()} issues found!")
        return

    for issue in issues:
        css_class = f"issue-{issue.severity}"
        icon = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}.get(issue.severity, "⚪")

        st.markdown(f"""
        <div class='{css_class}'>
            <strong>{icon} {issue.description}</strong>
            {f"<br><em>Location:</em> {issue.location}" if issue.location else ""}
            {f"<br><em>Recommendation:</em> {issue.recommendation}" if issue.recommendation else ""}
        </div>
        """, unsafe_allow_html=True)


def audit_article(url_or_id: str):
    """Run audit on a single article."""
    if not st.session_state.connected:
        st.error("Please connect to the APIs first.")
        return None

    client = st.session_state.zendesk_client
    analyzer = st.session_state.analyzer
    ui_verifier = st.session_state.ui_verifier

    with st.spinner("Fetching article..."):
        try:
            article = client.get_article(url_or_id)
        except Exception as e:
            st.error(f"Failed to fetch article: {str(e)}")
            return None

    with st.spinner("Analyzing content with Claude..."):
        try:
            analysis = analyzer.analyze(article)
        except Exception as e:
            st.error(f"Analysis failed: {str(e)}")
            return None

    with st.spinner("Verifying UI elements..."):
        try:
            ui_report = ui_verifier.verify_article(article.body)
        except Exception as e:
            st.warning(f"UI verification failed: {str(e)}")
            ui_report = None

    report = generate_report(article, analysis, ui_report)

    # Add to history
    st.session_state.audit_history.append({
        "title": report.article_title,
        "score": report.overall_score,
        "issues": report.total_issues,
        "url": report.article_url,
    })

    return report


def main():
    """Main application."""
    init_session_state()

    st.title("📝 Etsy Help Center Auditor")
    st.markdown("Audit help articles for content quality, technical accuracy, and Etsy style guidelines.")

    connect_services()

    # Main content area
    tab1, tab2, tab3 = st.tabs(["🔍 Single Article Audit", "📚 Batch Audit", "📊 Search Articles"])

    with tab1:
        st.header("Audit a Single Article")

        col1, col2 = st.columns([3, 1])
        with col1:
            article_input = st.text_input(
                "Article URL or ID",
                placeholder="https://help.etsy.com/hc/en-us/articles/123456789 or 123456789",
                help="Enter the full URL or just the article ID"
            )
        with col2:
            st.write("")  # Spacing
            st.write("")
            audit_button = st.button("🔍 Audit Article", type="primary", disabled=not st.session_state.connected)

        if audit_button and article_input:
            report = audit_article(article_input)

            if report:
                st.divider()

                # Article info
                st.subheader(report.article_title)
                st.caption(f"[View Article]({report.article_url})")

                # Score card
                render_score_card(report)

                st.divider()

                # Detailed findings in tabs
                findings_tabs = st.tabs([
                    "📋 Summary",
                    "✅ Actionable",
                    "📝 Brief",
                    "🎯 Targeted",
                    "⚙️ Technical",
                    "👥 Audience",
                    "🖥️ UI Verification"
                ])

                with findings_tabs[0]:
                    # Summary tab
                    if report.summary:
                        st.info(report.summary)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader("Audience")
                        st.write(f"**Declared:** {report.declared_audience}")
                        st.write(f"**Detected:** {report.detected_audience}")
                        if report.audience_mismatch:
                            st.error("⚠️ Audience mismatch detected!")

                    with col2:
                        st.subheader("Content Coverage")
                        st.write(f"Web instructions: {'✅' if report.has_web_instructions else '❌'}")
                        st.write(f"App instructions: {'✅' if report.has_app_instructions else '❌'}")

                    if report.member_services_flag:
                        st.error(f"⚠️ **Member Services Flag:** {report.flag_reason}")

                    # Download options
                    st.divider()
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            "📄 Download Report (Markdown)",
                            report.to_markdown(),
                            file_name=f"audit_{report.article_id}.md",
                            mime="text/markdown"
                        )
                    with col2:
                        st.download_button(
                            "📊 Download Report (JSON)",
                            report.to_json(),
                            file_name=f"audit_{report.article_id}.json",
                            mime="application/json"
                        )

                with findings_tabs[1]:
                    render_issues(report.actionable_issues, "Actionable")

                with findings_tabs[2]:
                    render_issues(report.brief_issues, "Brief")

                with findings_tabs[3]:
                    render_issues(report.targeted_issues, "Targeted")

                with findings_tabs[4]:
                    render_issues(report.technical_issues, "Technical")
                    if report.hardcoded_links:
                        st.warning("**Hardcoded Links Found:**")
                        for link in report.hardcoded_links:
                            st.code(link)

                with findings_tabs[5]:
                    render_issues(report.audience_issues, "Audience")

                with findings_tabs[6]:
                    st.write(f"**UI Elements Found:** {report.ui_elements_total}")
                    st.write(f"**Verified:** {report.ui_elements_verified}")
                    st.write(f"**Confidence:** {report.ui_confidence:.0%}")

                    if report.ui_manual_review_items:
                        st.warning("**Items Requiring Manual Review:**")
                        for item in report.ui_manual_review_items:
                            st.write(f"- {item}")

    with tab2:
        st.header("Batch Audit")
        st.info("Enter multiple article URLs or IDs, one per line.")

        batch_input = st.text_area(
            "Article URLs/IDs",
            height=150,
            placeholder="https://help.etsy.com/hc/en-us/articles/123456789\n123456790\n123456791"
        )

        if st.button("🔍 Audit All", type="primary", disabled=not st.session_state.connected):
            if batch_input:
                articles = [a.strip() for a in batch_input.split("\n") if a.strip()]
                results = []

                progress = st.progress(0)
                status = st.empty()

                for i, article in enumerate(articles):
                    status.text(f"Auditing {i+1}/{len(articles)}: {article[:50]}...")
                    report = audit_article(article)
                    if report:
                        results.append(report)
                    progress.progress((i + 1) / len(articles))

                status.text("Complete!")

                if results:
                    st.divider()
                    st.subheader("Batch Results Summary")

                    # Summary table
                    import pandas as pd
                    df = pd.DataFrame([
                        {
                            "Title": r.article_title[:40] + "...",
                            "Score": r.overall_score,
                            "Critical": len(r.critical_issues),
                            "Warnings": len(r.warnings),
                            "MS Flag": "Yes" if r.member_services_flag else "No"
                        }
                        for r in results
                    ])
                    st.dataframe(df, use_container_width=True)

                    # Download all reports
                    all_reports_md = "\n\n---\n\n".join([r.to_markdown() for r in results])
                    st.download_button(
                        "📄 Download All Reports",
                        all_reports_md,
                        file_name="batch_audit_report.md",
                        mime="text/markdown"
                    )

    with tab3:
        st.header("Search Articles")

        search_query = st.text_input("Search query", placeholder="refund policy")

        if st.button("🔍 Search", disabled=not st.session_state.connected):
            if search_query:
                with st.spinner("Searching..."):
                    try:
                        results = st.session_state.zendesk_client.search_articles(search_query)
                        if results:
                            for article in results[:10]:
                                with st.expander(article.title):
                                    st.write(f"**ID:** {article.id}")
                                    st.write(f"**URL:** {article.html_url}")
                                    if st.button(f"Audit", key=f"audit_{article.id}"):
                                        report = audit_article(str(article.id))
                        else:
                            st.info("No results found.")
                    except Exception as e:
                        st.error(f"Search failed: {str(e)}")


if __name__ == "__main__":
    main()
