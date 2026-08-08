import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from database import save_submission, fetch_category_statistics, get_existing_categories
import streamlit as st
from main import review_and_categorize_code, extract_category   
from database import save_submission
# Load API keys from your .env file
load_dotenv()
client=genai.Client()
# Configure the Gemini client
#GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#genai.configure(api_key=GEMINI_API_KEY)
def review_and_categorize_code(code_content: str) -> str:
    """Sends code or questions to Gemini and returns the AI response text, handling rate limits gracefully."""
    client = genai.Client()
    
    existing_categories = get_existing_categories()
    
    if existing_categories:
        categories_str = ", ".join([f"'{c}'" for c in existing_categories])
        category_instruction = (
            f"EXISTING CATEGORIES IN DATABASE: [{categories_str}]\n"
            "CRITICAL RULE: If the code snippet fits into ANY of the existing categories listed above "
            "(even if the concept or language varies slightly), you MUST output that EXACT string token for token.\n"
            "Only if it does NOT fit any existing category, create a new high-level general category name (1 to 3 words max)."
        )
    else:
        category_instruction = (
            "Create a single high-level general category name for this code (1 to 3 words max, e.g., 'Fibonacci', 'SQL Query', 'Prime Numbers')."
        )

    prompt = (
        "First, determine if the provided input is a CODE SNIPPET or a PROGRAMMING QUESTION.\n\n"
        "--- IF IT IS A CODE SNIPPET ---\n"
        "1. CATEGORY CLASSIFICATION:\n"
        f"{category_instruction}\n"
        "Format this line EXACTLY as: CATEGORY: <Chosen Category Name>\n"
        "2. CODE REVIEW:\n"
        "Provide a brief, constructive review covering performance, edge cases, and potential bugs.\n\n"
        "--- IF IT IS A PROGRAMMING QUESTION ---\n"
        "1. Format this line EXACTLY as: CATEGORY: NONE\n"
        "2. ANSWER:\n"
        "Provide a clear, accurate, and concise answer to the programming question."
    )

    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a specialized AI programming assistant. Your job is to analyze source code (review, debug, optimize) "
            "AND answer technical programming or software engineering questions.\n\n"
            "CRITICAL GUARDRAIL: If the provided input is off-topic, a casual greeting (like 'hello'), or completely unrelated to coding/programming, "
            "you MUST reply with exactly: 'I can only answer programming questions or analyze code.'"
        )
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=f"{prompt}\n\nUser Input:\n{code_content}",
            config=config
        )
        return response.text
    except APIError as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower():
            return "⚠️ **Reload API Key**: You have exceeded your free tier quota limit. Please wait a minute for the rate limit to reset, or check your API billing details."
        else:
            return f"⚠️ **API Error**: {e}"
    except Exception as e:
        return f"⚠️ **Unexpected Error**: {e}"
def extract_category(review_text: str) -> str:
    """Extracts the category tag from Gemini's output, handling markdown formatting."""
    for line in review_text.splitlines():
        # Remove any bold markdown like **CATEGORY:** -> CATEGORY:
        clean_line = line.replace("*", "").strip()
        
        # Check if line starts with CATEGORY (case-insensitive)
        if clean_line.upper().startswith("CATEGORY:"):
            # Split at the colon and take the right side
            parts = clean_line.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip().title()
                
    return "Uncategorized"

def main():
    print("======================================")
    print("     AI Code Reviewer CLI Started     ")
    print("======================================")

    if len(sys.argv) < 2:
        print("Error: No file provided!")
        print("Usage: py main.py <filename>")
        sys.exit(1)

    # Combine all arguments passed after main.py to support multi-line snippets
    user_input = " ".join(sys.argv[1:])

    # Check if user wants to see statistics
    if user_input.lower() == "show statistics":
        print("\n=== CLOUD STATISTICS ===")
        fetch_category_statistics()
        return

    # Only try to open as a file if the path ACTUALLY exists on disk
    if os.path.isfile(sys.argv[1]):
        file_path = os.path.normpath(sys.argv[1])
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                code_content = f.read()
            print(f"Successfully loaded file '{file_path}' ({len(code_content)} characters.)")
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    else:
        # Treat the input directly as a raw code snippet
        code_content = user_input
        print(f"Successfully loaded raw code snippet ({len(code_content)} characters.)")
    print("\nAnalyzing code with Gemini...")

    client = genai.Client()
    
    existing_categories = get_existing_categories()
    
    if existing_categories:
        categories_str = ", ".join([f"'{c}'" for c in existing_categories])
        category_instruction = (
            f"EXISTING CATEGORIES IN DATABASE: [{categories_str}]\n"
            "CRITICAL RULE: If the code snippet fits into ANY of the existing categories listed above "
            "(even if the concept or language varies slightly), you MUST output that EXACT string token for token.\n"
            "Only if it does NOT fit any existing category, create a new high-level general category name (1 to 3 words max)."
        )
    else:
        category_instruction = (
            "Create a single high-level general category name for this code (1 to 3 words max, e.g., 'Fibonacci', 'SQL Query', 'Prime Numbers')."
        )
    prompt = (
        "First, determine if the provided input is a CODE SNIPPET or a PROGRAMMING QUESTION.\n\n"
        "--- IF IT IS A CODE SNIPPET ---\n"
        "1. CATEGORY CLASSIFICATION:\n"
        f"{category_instruction}\n"
        "Format this line EXACTLY as: CATEGORY: <Chosen Category Name>\n"
        "2. CODE REVIEW:\n"
        "Provide a brief, constructive review covering performance, edge cases, and potential bugs.\n\n"
        "--- IF IT IS A PROGRAMMING QUESTION ---\n"
        "1. Format this line EXACTLY as: CATEGORY: NONE\n"
        "2. ANSWER:\n"
        "Provide a clear, accurate, and concise answer to the programming question."
    )
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a specialized AI programming assistant. Your job is to analyze source code (review, debug, optimize) "
            "AND answer technical programming or software engineering questions.\n\n"
            "CRITICAL GUARDRAIL: If the provided input is off-topic, a casual greeting (like 'hello'), or completely unrelated to coding/programming, "
            "you MUST reply with exactly: 'I can only answer programming questions or analyze code.'"
        )
    )
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=f"{prompt}\n\n```\n{code_content}\n```",
                config=config
            )
            print("\n=== AI CODE REVIEW RESULTS ===")
            print(response.text)
            category=extract_category(response.text)

            save_submission(code_content, category)
            return
        except APIError as e:
            if "503" in str(e) or "high demand" in str(e).lower():
                print(f"Server busy (Attempt {attempt}/3). Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"\nAPI Error: {e}")
                sys.exit(1)
        except Exception as e:
            print(f"\nUnexpected Error: {e}")
            sys.exit(1)
            
    print("\nError: The model is experiencing high demand. Please try again shortly.")

if __name__ == "__main__":
    main()
