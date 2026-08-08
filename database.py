# database.py
import os
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_or_create_user_id() -> str:
    """Gets the local anonymous user ID for CLI use, creating one if it doesn't exist."""
    device_file = ".device_id"
    if os.path.exists(device_file):
        with open(device_file, "r") as f:
            return f.read().strip()
    else:
        new_id = str(uuid.uuid4())
        with open(device_file, "w") as f:
            f.write(new_id)
        return new_id


def save_submission(
    code_content: str,
    category: str = "Uncategorized",
    review_text: str = "",
    user_id: str = None,
    severity: str = "Unknown",
):
    """Saves a valid code submission to Supabase, including the AI review text and severity."""
    if user_id is None:
        user_id = get_or_create_user_id()

    try:
        supabase.table("submissions").insert({
            "user_id": user_id,
            "code_content": code_content,
            "category": category,
            "review_text": review_text,
            "severity": severity,
        }).execute()
    except Exception as e:
        print(f"Error saving to database: {e}")


def fetch_category_statistics():
    """
    Derives category stats directly from the submissions table.
    Displays total submissions and the top 3 categories.
    """
    try:
        response = supabase.table("submissions").select("category").execute()
        rows = response.data

        if not rows:
            print("No statistics found yet. Submit some code snippets first!")
            return

        counts: dict[str, int] = {}
        for row in rows:
            cat = row.get("category", "")
            if cat and cat.upper() not in ("UNCATEGORIZED", "NONE"):
                counts[cat] = counts.get(cat, 0) + 1

        if not counts:
            print("No categorized submissions found yet!")
            return

        total_submissions = sum(counts.values())
        sorted_stats = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        top_3 = sorted_stats[:3]

        print(f"Total Submissions Tracked: {total_submissions}\n")
        print("--- Top 3 Most Popular Categories ---")
        for rank, (category_name, count) in enumerate(top_3, start=1):
            percentage = (count / total_submissions) * 100
            print(f"{rank}. {category_name}")
            print(f"   - Submissions: {count}")
            print(f"   - Share: {percentage:.2f}%\n")

    except Exception as e:
        print(f"Error fetching statistics: {e}")


def get_existing_categories() -> list[str]:
    """
    Derives distinct category names directly from the submissions table.
    No longer depends on the category_stats table.
    """
    try:
        response = supabase.table("submissions").select("category").execute()
        seen = set()
        categories = []
        for row in response.data:
            cat = row.get("category", "")
            if cat and cat.upper() not in ("UNCATEGORIZED", "NONE") and cat not in seen:
                seen.add(cat)
                categories.append(cat)
        return categories
    except Exception as e:
        print(f"Warning: Could not fetch existing categories: {e}")
        return []


def fetch_submission_history(user_id: str = None) -> list[dict]:
    """
    Fetches past submissions ordered by newest first, filtered by user_id if provided.
    """
    try:
        query = (
            supabase.table("submissions")
            .select("id, code_content, category, review_text, created_at, severity")
            .order("created_at", desc=True)
        )
        if user_id:
            query = query.eq("user_id", user_id)
        return query.execute().data or []
    except Exception as e:
        print(f"Error fetching submission history: {e}")
        return []

def delete_submission(submission_id: str):
    """Deletes a submission from Supabase by its ID."""
    try:
        supabase.table("submissions").delete().eq("id", submission_id).execute()
    except Exception as e:
        print(f"Error deleting submission: {e}")