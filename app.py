"""
Etsy Help Center Auditor - Streamlit Web Application
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
    try:
        if hasattr(st, 'secrets') and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


st.set_page_config(
    page_title="Etsy Help Center Auditor",
    page_icon="📝",
    layout="wide",
)

st.markdown("""
<style>
    .score-excellent { color: #28a745; font-size: 2em; font-weight: bold; }
    .score-good { color: #5cb85c; font-size: 2em; font-weight: bold; }
    .score-needswork { color: #f0ad4e; font-size: 2em; font-weight: bold; }
    .score-critical { color: #d9534f; font-size: 2em; font-weight: bold; }
    .issue-critical { background-color: #f8d7da; padding: 10px; border-radius: 5px; margin: 5px 0; }
    .issue-warning { background-color: #fff3cd; padding: 10px; border-radius: 5px; margin: 5px 0; }
    .issue-suggestion { background-color: #d1ecf1; padding: 10px; border-radius: 5px; margin: 5px 0; }
</style>
""", unsafe_allow_html=True)


def init_session_state():
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
    with st.sidebar:
        st.header("🔐 Configuration")

        zendesk_email = get_secret("ZENDESK_EMAIL")
        zendesk_token = get_secret("ZENDESK_API_TOKEN")
        anthropic_key = get_secret("ANTHROPIC_API_KEY")

        zendesk_email = st.text_input("Zendesk Email", value=zendesk_email)
        zendesk_token = st.text_input("Zendesk API Token", value=zendesk_token, type="password")
        anthropic_key = st.text_input("Anthropic API Key", value=anthropic_key, type="password")

        if st.button("Connect", type="primary"):
            with st.spinner("Connecting..."):
                try:
                    client = ZendeskClient(
                        subdomain="etsy",
                        email=zendesk_email,
                        api_token=zendesk_token
                    )
                    if not client.test_connection():
                        st.error("Failed to connect to Zendesk.")
                        return
                    analyzer = ContentAnalyzer(api_key=anthropic_key)
                    st.session_state.zendesk_client = client
                    st.session_state.analyzer = analyzer
                    st.session_state.connected = True
                    st.success("Connected!")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        if st.session_state.connected:
            st.success("✓ Connected")
        else:
            st.warning("Not connected")


def render_score_card(report):
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
        st.metric("Critical", len(report.critical_issues))
    with col3:
        st.metric("Warnings", len(report.warnings))
    with col4:
        st.metric("Suggestions", len(report.suggestions))


def render_issues(issues, category_name):
    if not issues:
        st.success(f"No {category_name.lower()} issues!")
        return
    for issue in issues:
        css_class = f"issue-{issue.severity}"
        icon = {"critical": "🔴", "warning": "🟡", "suggestion": "🔵"}.get(issue.severity, "⚪")
        st.markdown(f"""
        <div class='{css_class}'>
            <strong>{icon} {issue.description}</strong>
            {f"<br><em>Location:</em> {issue.location}" if issue.location else ""}
            {f"<br><em>Fix:</em> {issue.recommendation}" if issue.recommendation else ""}
        </div>
        """, unsafe_allow_html=True)


def audit_article(url_or_id: str):
    if not st.session_state.connected:
        st.error("Please connect first.")
        return None

    client = st.session_state.zendesk_client
    analyzer = st.session_state.analyzer
    ui_verifier = st.session_state.ui_verifier

    with st.spinner("Fetching article..."):
        try:
            article = client.get_article(url_or_id)
        except Exception as e:
            st.error(f"Fetch failed: {str(e)}")
            return None

    with st.spinner("Analyzing with Claude..."):
        try:
            analysis = analyzer.analyze(article)
        except Exception as e:
            st.error(f"Analysis failed: {type(e).__name__}: {str(e)}")
            return None

    with st.spinner("Verifying UI..."):
        try:
            ui_report = ui_verifier.verify_article(article.body)
        except Exception:
            ui_report = None

    report = generate_report(article, analysis, ui_report)
    st.session_state.audit_history.append({
        "title": report.article_title,
        "score": report.overall_score,
        "issues": report.total_issues,
    })
    return report


def main():
    init_session_state()

    st.title("📝 Etsy Help Center Auditor")
    st.markdown("Audit help articles for quality and Etsy style guidelines.")

    connect_services()

    tab1, tab2, tab3 = st.tabs(["🔍 Single Audit", "📚 Batch Audit", "📊 Search"])

    with tab1:
        st.header("Audit a Single Article")
        col1, col2 = st.columns([3, 1])
        with col1:
            article_input = st.text_input("Article URL or ID", placeholder="https://help.etsy.com/hc/en-us/articles/123456789")
        with col2:
            st.write("")
            st.write("")
            audit_button = st.button("🔍 Audit", type="primary", disabled=not st.session_state.connected)

        if audit_button and article_input:
            report = audit_article(article_input)
            if report:
                st.divider()
                st.subheader(report.article_title)
                st.caption(f"[View Article]({report.article_url})")
                render_score_card(report)
                st.divider()

                findings_tabs = st.tabs(["📋 Summary", "✅ Actionable", "📝 Brief", "🎯 Targeted", "⚙️ Technical", "👥 Audience"])

                with findings_tabs[0]:
                    if report.summary:
                        st.info(report.summary)
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Declared Audience:** {report.declared_audience}")
                        st.write(f"**Detected Audience:** {report.detected_audience}")
                        if report.audience_mismatch:
                            st.error("⚠️ Audience mismatch!")
                    with col2:
                        st.write(f"Web instructions: {'✅' if report.has_web_instructions else '❌'}")
                        st.write(f"App instructions: {'✅' if report.has_app_instructions else '❌'}")
                    if report.member_services_flag:
                        st.error(f"⚠️ Member Services Flag: {report.flag_reason}")
                    st.divider()
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button("📄 Download Markdown", report.to_markdown(), file_name=f"audit_{report.article_id}.md")
                    with col2:
                        st.download_button("📊 Download JSON", report.to_json(), file_name=f"audit_{report.article_id}.json")

                with findings_tabs[1]:
                    render_issues(report.actionable_issues, "Actionable")
                with findings_tabs[2]:
                    render_issues(report.brief_issues, "Brief")
                with findings_tabs[3]:
                    render_issues(report.targeted_issues, "Targeted")
                with findings_tabs[4]:
                    render_issues(report.technical_issues, "Technical")
                    if report.hardcoded_links:
                        st.warning("**Hardcoded Links:**")
                        for link in report.hardcoded_links:
                            st.code(link)
                with findings_tabs[5]:
                    render_issues(report.audience_issues, "Audience")

    with tab2:
        st.header("Batch Audit")
        batch_input = st.text_area("Article URLs/IDs (one per line)", height=150)
        if st.button("🔍 Audit All", type="primary", disabled=not st.session_state.connected):
            if batch_input:
                articles = [a.strip() for a in batch_input.split("\n") if a.strip()]
                results = []
                progress = st.progress(0)
                for i, article in enumerate(articles):
                    report = audit_article(article)
                    if report:
                        results.append(report)
                    progress.progress((i + 1) / len(articles))
                if results:
                    import pandas as pd
                    df = pd.DataFrame([{
                        "Title": r.article_title[:40],
                        "Score": r.overall_score,
                        "Critical": len(r.critical_issues),
                        "Warnings": len(r.warnings),
                    } for r in results])
                    st.dataframe(df, use_container_width=True)
                    all_reports = "\n\n---\n\n".join([r.to_markdown() for r in results])
                    st.download_button("📄 Download All", all_reports, file_name="batch_audit.md")

    with tab3:
        st.header("Search Articles")
        search_query = st.text_input("Search", placeholder="refund policy")
        if st.button("🔍 Search", disabled=not st.session_state.connected):
            if search_query:
                with st.spinner("Searching..."):
                    try:
                        results = st.session_state.zendesk_client.search_articles(search_query)
                        if results:
                            for article in results[:10]:
                                with st.expander(article.title):
                                    st.write(f"ID: {article.id}")
                                    st.write(f"URL: {article.html_url}")
                        else:
                            st.info("No results.")
                    except Exception as e:
                        st.error(f"Search failed: {str(e)}")


if __name__ == "__main__":
    main()
