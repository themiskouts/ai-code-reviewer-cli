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

#Custom CSS & Flexbox Header
# REPLACE YOUR EXISTING st.markdown(...) BLOCK WITH THIS:
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

# Sidebar setup
with st.sidebar:
  st.header("Navigation")
  st.write("History & Saved Snippets")

# Code input text area
code_input = st.text_area(
    "Paste your source code here for review:", height=200
)

# Action button
if st.button("Review Code"):
  if code_input:
    with st.spinner("Analyzing code with AI..."):
      try:
        # 1. Call backend function
        review_text = review_and_categorize_code(code_input)

        # 2. Extract category
        category = extract_category(review_text)

        # 3. Save to Supabase
        save_submission(code_input, category)

        # 4. Display styled Category Header
        st.subheader(f"Category: {category}")

        # 5. Filter out the redundant CATEGORY: line from Gemini's output
        cleaned_review = "\n".join(
            line
            for line in review_text.splitlines()
            if not line.strip().upper().startswith("CATEGORY:")
        ).strip()

        st.write(cleaned_review)
        st.toast(f"Saved under category '{category}' in Supabase!", icon="💾")

      except Exception as e:
        st.error(f"An error occurred: {e}")
  else:
    st.warning("Please paste some code first.")