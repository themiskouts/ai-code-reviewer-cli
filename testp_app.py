import streamlit as st
from database import save_submission
from main import extract_category, review_and_categorize_code
import base64

st.set_page_config(
    page_title="AsterAI - Code Analyzing",
    page_icon="logo.png",
    layout="centered",
)

# Function to load your logo image into HTML
def get_base64_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode()

logo_b64 = get_base64_image("logo.png")

# Custom CSS & Flexbox Header
st.markdown(
    f"""
    <style>
        /* Pushes content down past Streamlit's top navbar */
        .block-container {{
            padding-top: 5.5rem !important;
        }}
    </style>
    
    <div style="display: flex; align-items: center; gap: 20px; margin-bottom: 30px;">
        <img src="data:image/png;base64,{logo_b64}" style="width: 90px; height: 90px; border-radius: 14px; object-fit: contain; flex-shrink: 0; display: block;">
        <h1 style="margin: 0; padding: 0; font-size: 2.8rem; font-weight: 700; line-height: 1; color: inherit; border: none;">
            AsterAI - Code Analyzing
        </h1>
    </div>
    """,
    unsafe_allow_html=True,
)

# Sidebar setup with Synchronized Analytics Toggle
with st.sidebar:
    st.header("Navigation")
    st.write("History & Saved Snippets")
    
    st.markdown("---")
    st.subheader("📊 Analytics")

    # Initialize session state
    if "show_stats" not in st.session_state:
        st.session_state.show_stats = False

    # Check state and render the correct button and content instantly
    if st.session_state.show_stats:
        # 1. Render Close button
        if st.button("❌ Close Statistics"):
            st.session_state.show_stats = False
            st.rerun()
            
        # 2. Render statistics content right below it
        try:
            from database import supabase
            response = supabase.table("category_stats").select("*").execute()
            stats_data = response.data
            
            if not stats_data:
                st.info("No statistics found yet!")
            else:
                valid_stats = [
                    item for item in stats_data 
                    if item["category_name"] and item["category_name"].upper() not in ["UNCATEGORIZED", "NONE"]
                ]
                
                if not valid_stats:
                    st.info("No categorized submissions found yet!")
                else:
                    total_submissions = sum(item["count"] for item in valid_stats)
                    sorted_stats = sorted(valid_stats, key=lambda x: x["count"], reverse=True)
                    
                    st.metric("Total Submissions", total_submissions)
                    st.markdown("**Top Categories:**")
                    
                    for item in sorted_stats[:3]:
                        cat_name = item["category_name"]
                        count = item["count"]
                        share = (count / total_submissions) * 100 if total_submissions > 0 else 0
                        st.write(f"- **{cat_name}**: {count} ({share:.1f}%)")
        except Exception as e:
            st.error(f"Error loading stats: {e}")
            
    else:
        # Render View button when stats are closed
        if st.button("📊 View Cloud Statistics"):
            st.session_state.show_stats = True
            st.rerun()

# File Uploader and Code Input Text Area
uploaded_file = st.file_uploader("Upload a code file:", type=['py', 'js', 'cpp', 'c', 'java', 'html', 'css', 'txt'])
code_input = st.text_area(
    "Or paste your source code here for review:", height=200
)

# Action button
if st.button("Review Code"):
    # Priority: Uploaded file content takes precedence over text area
    if uploaded_file is not None:
        content_to_analyze = uploaded_file.read().decode("utf-8")
    else:
        content_to_analyze = code_input

    if content_to_analyze:
        # 1. Create an empty container for our dynamic loader/gear
        status_placeholder = st.empty()

        # Render the spinning gear animation live
        status_placeholder.markdown("""
            <style>
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .spinning-gear {
                display: inline-block;
                animation: spin 1.5s linear infinite;
            }
            </style>
            <div style="display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 500; padding: 10px 0;">
                <span class="spinning-gear" style="font-size: 22px;">⚙️</span> Analyzing code with AI...
            </div>
        """, unsafe_allow_html=True)

        try:
            # 2. Call backend function
            review_text = review_and_categorize_code(content_to_analyze)

            # Check if it's an API quota / rate limit warning
            if "Reload API Key" in review_text or "⚠️" in review_text:
                status_placeholder.empty()
                st.warning(review_text)
            else:
                # 3. Extract category
                category = extract_category(review_text)

                # 4. Save to Supabase (Only if it's a valid code category, not NONE)
                if category.upper() != "NONE" and "I can only answer" not in review_text:
                    save_submission(content_to_analyze, category)

                # 5. Instantly swap gear to a green checkmark!
                status_placeholder.markdown("""
                    <div style="display: flex; align-items: center; gap: 10px; font-size: 16px; font-weight: 500; color: #28a745; padding: 10px 0;">
                        <span style="font-size: 22px;">✅</span> Analysis complete!
                    </div>
                """, unsafe_allow_html=True)

                # 6. Display styled Category Header
                st.subheader(f"Category: {category}")

                # 7. Filter out the redundant CATEGORY: line from Gemini's output
                cleaned_review = "\n".join(
                    line
                    for line in review_text.splitlines()
                    if not line.strip().upper().startswith("CATEGORY:")
                ).strip()

                st.write(cleaned_review)
                
                if category.upper() != "NONE":
                    st.toast(f"Saved under category '{category}' in Supabase!", icon="💾")

        except Exception as e:
            status_placeholder.empty()
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please upload a file or paste some code first.")