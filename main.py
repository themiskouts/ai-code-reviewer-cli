import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from database import save_submission, fetch_category_statistics, get_existing_categories
# Load API keys from your .env file
load_dotenv()
client=genai.Client()
# Configure the Gemini client
#GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
#genai.configure(api_key=GEMINI_API_KEY)

def review_and_categorize_code(code_content: str):
    """Sends code to Gemini for analysis and extracts a specific category."""
    
    prompt = f"""
    You are an expert code reviewer and technical tutor.
    Analyze the following code snippet and perform two tasks:

    1. CATEGORY: Provide a single, highly specific classification tag describing the core algorithm, concept, or feature implemented in the code.
       - Good examples: "Dijkstra's Algorithm", "Prime Number Checking", "SQL Table Creation", "Binary Search Tree", "C File I/O".
       - Bad examples: "Math", "Algorithms", "C++", "Data Structures", "Loops".
       - Format this line EXACTLY as: CATEGORY: <Your Specific Category>

    2. REVIEW: Provide a brief, constructive code review highlighting performance, edge cases, readability, and potential bugs.

    Here is the code to review:
    ```
    {code_content}
    ```
    """

    # Query Gemini
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt
    )
    return response.text

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
    prompt = (
        "Analyze the provided source code snippet and perform two tasks:\n\n"
        "1. CATEGORY CLASSIFICATION:\n"
        "   - Identify the single core concept, underlying algorithm, domain, or primary subject of the code.\n"
        "   - Abstraction Rule: Do NOT include implementation details, data structures used, or specific method names (e.g., prefer 'Fibonacci' over 'Recursive Fibonacci Sequence Calculation', 'SQL Queries' over 'SQL Inner Join', 'Prime Numbers' over 'Trial Division Prime Check').\n"
        "   - Generalization Rule: Produce a general, high-level category name consisting of 1 to 3 words maximum. Capitalize each word cleanly.\n"
        "   - Format this line EXACTLY as: CATEGORY: <General Category Name>\n\n"
        "2. CODE REVIEW:\n"
        "   - Provide a brief, constructive review covering performance, edge cases, and potential bugs."
    )
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a strict code review assistant. Your ONLY job is to analyze source code "
            "(such as Python, C, JavaScript, etc.). "
            "If the provided input is plain text, a general question, or anything that is not actual source code, "
            "you MUST reply with exactly: 'I can only answer about analyzing code.' "
            "Do not answer any other queries or perform general chat tasks."
        )
    )
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
        "Analyze the provided source code snippet and perform two tasks:\n\n"
        "1. CATEGORY CLASSIFICATION:\n"
        f"{category_instruction}\n"
        "Format this line EXACTLY as: CATEGORY: <Chosen Category Name>\n\n"
        "2. CODE REVIEW:\n"
        "Provide a brief, constructive review covering performance, edge cases, and potential bugs."
    )
    config = types.GenerateContentConfig(
        system_instruction=(
            "You are a strict code review assistant. Your ONLY job is to analyze source code "
            "(such as Python, C, JavaScript, etc.). "
            "If the provided input is plain text, a general question, or anything that is not actual source code, "
            "you MUST reply with exactly: 'I can only answer about analyzing code.' "
            "Do not answer any other queries or perform general chat tasks."
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