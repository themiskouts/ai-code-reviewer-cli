# testp_app.py
import uuid
import base64
import streamlit as st
from database import save_submission, fetch_submission_history, delete_submission
from main import extract_category, review_and_categorize_code, detect_language, extract_severity
st.set_page_config(
    page_title="AsterAI - Code Analyzing",
    page_icon="logo.png",
    layout="centered",
)


# ── Session state bootstrap ──────────────────────────────────────────────────

if "web_user_id" not in st.session_state:
    st.session_state["web_user_id"] = str(uuid.uuid4())

if "code_input_area" not in st.session_state:
    st.session_state["code_input_area"] = ""

if "past_review_display" not in st.session_state:
    st.session_state["past_review_display"] = None

if "show_stats" not in st.session_state:
    st.session_state["show_stats"] = False

if "history_cache" not in st.session_state:
    st.session_state["history_cache"] = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_base64_image(image_path: str) -> str:
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()


def format_timestamp(ts_str: str) -> str:
    """Converts a UTC ISO timestamp from Supabase to Greek Time (DD/MM/YYYY at HH:MM)."""
    try:
        from datetime import datetime, timezone
        import zoneinfo
        dt_utc = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
        dt_athens = dt_utc.astimezone(zoneinfo.ZoneInfo("Europe/Athens"))
        return dt_athens.strftime("%d/%m/%Y at %H:%M")
    except Exception:
        return ts_str


def truncate(text: str, max_len: int = 25) -> str:
    text = text.strip().replace("\n", " ")
    return text if len(text) <= max_len else text[:max_len].rstrip() + "…"

def severity_badge(severity: str) -> str:
    """Returns an HTML badge string for a given severity level."""
    config = {
        "Clean":           ("✅", "#28a745"),
        "Needs Work":      ("⚠️", "#e0a800"),
        "Critical Issues": ("🔴", "#dc3545"),
    }
    icon, color = config.get(severity, ("❓", "#6c757d"))
    return (
        f"<span style='background:{color};color:white;padding:4px 10px;"
        f"border-radius:12px;font-size:0.8rem;font-weight:600;'>"
        f"{icon} {severity}</span>"
    )


# ── Header ───────────────────────────────────────────────────────────────────

logo_b64 = get_base64_image("logo.png")

st.markdown(
    f"""
    <style>
        .block-container {{ padding-top: 5.5rem !important; }}
    </style>
    <div style="display:flex;align-items:center;gap:20px;margin-bottom:30px;">
        <img src="data:image/png;base64,{logo_b64}"
             style="width:90px;height:90px;border-radius:14px;object-fit:contain;flex-shrink:0;">
        <h1 style="margin:0;padding:0;font-size:2.8rem;font-weight:700;line-height:1;border:none;">
            AsterAI - Code Analyzing
        </h1>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Navigation")

    # ── Analytics ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📊 Analytics")

    if st.session_state.show_stats:
        if st.button("❌ Close Statistics"):
            st.session_state.show_stats = False
            st.rerun()

        try:
            history = fetch_submission_history()
            valid = [
                r for r in history
                if r.get("category", "").upper() not in ("UNCATEGORIZED", "NONE", "")
            ]
            if not valid:
                st.info("No categorized submissions found yet!")
            else:
                counts: dict[str, int] = {}
                for r in valid:
                    cat = r["category"]
                    counts[cat] = counts.get(cat, 0) + 1

                total = sum(counts.values())
                st.metric("Total Submissions", total)
                st.markdown("**Top Categories:**")
                for cat, cnt in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]:
                    share = (cnt / total) * 100
                    st.write(f"- **{cat}**: {cnt} ({share:.1f}%)")
        except Exception as e:
            st.error(f"Error loading stats: {e}")
    else:
        if st.button("📊 View Cloud Statistics"):
            st.session_state.show_stats = True
            st.rerun()

    # ── History ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🕓 History")

    if "show_history" not in st.session_state:
        st.session_state["show_history"] = False

    if st.session_state["show_history"]:
        if st.button("❌ Close History"):
            st.session_state["show_history"] = False
            st.rerun()

        search_query = st.text_input("Search history", placeholder="Filter by category or code…")

        if st.session_state["history_cache"] is None:
            st.session_state["history_cache"] = fetch_submission_history()
        history_rows = st.session_state["history_cache"]

        if not history_rows:
            st.info("No past submissions yet.")
        else:
            filtered = [
                r for r in history_rows
                if not search_query
                or search_query.lower() in r.get("category", "").lower()
                or search_query.lower() in r.get("code_content", "").lower()
            ]

            if not filtered:
                st.warning("No results match your search.")

            for row in filtered:
                category = row.get("category", "Uncategorized")
                ts = format_timestamp(row.get("created_at", ""))
                code_snippet = row.get("code_content", "")
                review = row.get("review_text", "")
                title = f"📦 {category} ({ts})"
                short_title = truncate(title, 40)

                sev = row.get("severity", "Unknown")
                with st.expander(short_title):
                    st.markdown(
                        severity_badge(sev),
                        unsafe_allow_html=True,
                    )
                    st.markdown("**Submitted Code:**")
                    detected = detect_language(review or "", code_snippet)
                    st.code(code_snippet, language=detected)

                    if review:
                        st.markdown("**AsterAI Review:**")
                        cleaned = "\n".join(
                            line for line in review.splitlines()
                            if not line.strip().upper().startswith("CATEGORY:")
                        ).strip()
                        st.write(cleaned)

                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if st.button("📂 Load into Editor & View Analysis", key=f"load_{row['id']}"):
                            st.session_state["code_input_area"] = code_snippet
                            st.session_state["past_review_display"] = {
                                "category": category,
                                "review": review,
                            }
                            st.rerun()
                    with col2:
                        if st.button("🗑️", key=f"delete_{row['id']}", help="Delete this submission"):
                            delete_submission(row["id"])
                            st.session_state["history_cache"] = None
                            st.toast("Submission deleted.", icon="🗑️")
                            st.rerun()
    else:
        if st.button("🕓 View History"):
            st.session_state["show_history"] = True
            st.rerun()


# ── Main content ─────────────────────────────────────────────────────────────

uploaded_file = st.file_uploader(
    "Upload a code file:",
    type=["py", "js", "cpp", "c", "java", "html", "css", "txt"],
)

code_input = st.text_area(
    "Or paste your source code here for review:",
    height=200,
    key="code_input_area",
)

if st.button("Review Code"):
    content_to_analyze = (
        uploaded_file.read().decode("utf-8") if uploaded_file is not None else code_input
    )

    if content_to_analyze:
        # Clear any previously loaded historical review
        st.session_state["past_review_display"] = None

        status_placeholder = st.empty()
        status_placeholder.markdown("""
            <style>
            @keyframes spin { 0%{transform:rotate(0deg);} 100%{transform:rotate(360deg);} }
            .spinning-gear { display:inline-block; animation:spin 1.5s linear infinite; }
            </style>
            <div style="display:flex;align-items:center;gap:10px;font-size:16px;font-weight:500;padding:10px 0;">
                <span class="spinning-gear" style="font-size:22px;">⚙️</span> Analyzing code with AI...
            </div>
        """, unsafe_allow_html=True)

        try:
            review_text = review_and_categorize_code(content_to_analyze)

            if "Reload API Key" in review_text or "⚠️" in review_text:
                status_placeholder.empty()
                st.warning(review_text)
            else:
                category = extract_category(review_text)
                is_valid_category = (
                    category.upper() not in ("NONE", "UNCATEGORIZED")
                    and "I can only answer" not in review_text
                )

                detected_lang = detect_language(review_text, content_to_analyze)
                severity = extract_severity(review_text)

                if is_valid_category:
                    save_submission(
                        content_to_analyze,
                        category,
                        review_text=review_text,
                        user_id=st.session_state["web_user_id"],
                        severity=severity,
                    )
                    st.session_state["history_cache"] = None

                status_placeholder.markdown("""
                    <div style="display:flex;align-items:center;gap:10px;font-size:16px;
                                font-weight:500;color:#28a745;padding:10px 0;">
                        <span style="font-size:22px;">✅</span> Analysis complete!
                    </div>
                """, unsafe_allow_html=True)

                col_cat, col_lang, col_sev = st.columns([3, 1, 1])
                with col_cat:
                    st.subheader(f"Category: {category}")
                with col_lang:
                    st.markdown(
                        f"<div style='margin-top:1.6rem;'>"
                        f"<span style='background:#2E86DE;color:white;padding:4px 10px;"
                        f"border-radius:12px;font-size:0.8rem;font-weight:600;'>"
                        f"🖥️ {detected_lang.upper()}</span></div>",
                        unsafe_allow_html=True,
                    )
                with col_sev:
                    st.markdown(
                        f"<div style='margin-top:1.6rem;'>{severity_badge(severity)}</div>",
                        unsafe_allow_html=True,
                    )

                cleaned_review = "\n".join(
                    line for line in review_text.splitlines()
                    if not line.strip().upper().startswith("CATEGORY:")
                ).strip()
                st.write(cleaned_review)

                if is_valid_category:
                    st.toast(f"Saved under category '{category}' in Supabase!", icon="💾")

        except Exception as e:
            status_placeholder.empty()
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please upload a file or paste some code first.")


# ── Historical review display (loaded from sidebar) ───────────────────────────

if st.session_state.get("past_review_display"):
    data = st.session_state["past_review_display"]
    st.divider()
    st.subheader(f"📂 Loaded Analysis — Category: {data['category']}")
    if data["review"]:
        cleaned = "\n".join(
            line for line in data["review"].splitlines()
            if not line.strip().upper().startswith("CATEGORY:")
        ).strip()
        st.write(cleaned)
    else:
        st.info("No review text was stored for this submission.")