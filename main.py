# main.py
import os
import sys
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import APIError
from database import save_submission, fetch_category_statistics, get_existing_categories

load_dotenv()

MODEL_NAME = "gemini-2.0-flash"


def _build_prompt_and_config(code_content: str) -> tuple[str, types.GenerateContentConfig]:
    """Builds the categorization prompt and model config for a given input."""
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
            "Create a single high-level general category name for this code "
            "(1 to 3 words max, e.g., 'Fibonacci', 'SQL Query', 'Prime Numbers')."
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
            "You are a specialized AI programming assistant. Your job is to analyze source code "
            "(review, debug, optimize) AND answer technical programming or software engineering questions.\n\n"
            "CRITICAL GUARDRAIL: If the provided input is off-topic, a casual greeting (like 'hello'), "
            "or completely unrelated to coding/programming, "
            "you MUST reply with exactly: 'I can only answer programming questions or analyze code.'"
        )
    )

    return prompt, config


def review_and_categorize_code(code_content: str) -> str:
    """Tries Gemini first, falls back to Groq on quota errors."""
    prompt, config = _build_prompt_and_config(code_content)
    system_instruction = config.system_instruction

    # ── Attempt 1: Gemini ─────────────────────────────────────────────────
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"{prompt}\n\nUser Input:\n{code_content}",
            config=config,
        )
        return response.text
    except APIError as e:
        is_quota = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "quota" in str(e).lower()
        if not is_quota:
            return f"⚠️ **API Error**: {e}"
        print("Gemini quota hit — falling back to Groq...")

    # ── Attempt 2: Groq fallback ──────────────────────────────────────────
    try:
        from groq import Groq
        groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        groq_response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user",   "content": f"{prompt}\n\nUser Input:\n{code_content}"},
            ],
            max_tokens=1000,
        )
        return groq_response.choices[0].message.content
    except Exception as e:
        return (
            f"⚠️ **Both Gemini and Groq failed.**\n"
            f"Gemini: quota exceeded. Groq: {e}\n\n"
            "Please wait a minute and try again."
        )


def extract_category(review_text: str) -> str:
    """Extracts the category tag from Gemini's output, handling markdown formatting."""
    for line in review_text.splitlines():
        clean_line = line.replace("*", "").strip()
        if clean_line.upper().startswith("CATEGORY:"):
            parts = clean_line.split(":", 1)
            if len(parts) > 1 and parts[1].strip():
                return parts[1].strip().title()
    print("Warning: Could not parse CATEGORY line from AI response. Defaulting to 'Uncategorized'.")
    return "Uncategorized"

def extract_severity(review_text: str) -> str:
    """
    Asks the AI response to self-rate severity, or infers it from keywords.
    Returns one of: 'Clean', 'Needs Work', 'Critical Issues'
    """
    review_lower = (review_text or "").lower()

    critical_keywords = [
        "critical", "severe", "dangerous", "vulnerability", "exploit",
        "crash", "memory leak", "injection", "overflow", "deadlock",
        "infinite loop", "data loss", "security risk"
    ]
    warning_keywords = [
        "inefficient", "edge case", "unhandled", "missing", "should",
        "consider", "improve", "potential bug", "could fail", "not optimal",
        "no error handling", "avoid", "recommend", "issue"
    ]

    for kw in critical_keywords:
        if kw in review_lower:
            return "Critical Issues"

    for kw in warning_keywords:
        if kw in review_lower:
            return "Needs Work"

    return "Clean"

def detect_language(review_text: str, code_content: str) -> str:
    """
    Detects programming language from AI output first,
    then falls back to simple extension/keyword heuristics.
    """
    # Check if Gemini mentioned the language in its review
    review_lower = (review_text or "").lower()
    language_map = {
        "javascript": "javascript",
        "typescript": "typescript",
        "python": "python",
        "java": "java",
        "c++": "cpp",
        "cpp": "cpp",
        "c#": "csharp",
        "sql": "sql",
        "html": "html",
        "css": "css",
        "bash": "bash",
        "shell": "bash",
        "rust": "rust",
        "go": "go",
        "php": "php",
        "ruby": "ruby",
        "swift": "swift",
        "kotlin": "kotlin",
    }
    for keyword, lang in language_map.items():
        if keyword in review_lower:
            return lang

    # Keyword heuristics on the code itself
    if "def " in code_content or "import " in code_content and "from " in code_content:
        return "python"
    if "function " in code_content or "const " in code_content or "=>" in code_content:
        return "javascript"
    if "#include" in code_content:
        return "cpp"
    if "SELECT " in code_content.upper() or "FROM " in code_content.upper():
        return "sql"
    if "<html" in code_content.lower():
        return "html"

    return "python"  # safe default

def main():
    print("======================================")
    print("     AI Code Reviewer CLI Started     ")
    print("======================================")

    if len(sys.argv) < 2:
        print("Error: No file provided!")
        print("Usage: py main.py <filename|code_snippet>")
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])

    if user_input.lower() == "show statistics":
        print("\n=== CLOUD STATISTICS ===")
        fetch_category_statistics()
        return

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
        code_content = user_input
        print(f"Successfully loaded raw code snippet ({len(code_content)} characters.)")

    print("\nAnalyzing code with Gemini...")

    client = genai.Client()
    prompt, config = _build_prompt_and_config(code_content)

    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=f"{prompt}\n\n```\n{code_content}\n```",
                config=config,
            )
            review_text = response.text
            print("\n=== AI CODE REVIEW RESULTS ===")
            print(review_text)

            category = extract_category(review_text)
            save_submission(code_content, category, review_text=review_text)
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