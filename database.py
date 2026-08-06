import os
import uuid
from supabase import create_client, Client
from dotenv import load_dotenv
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
def get_or_create_user_id() -> str:
    """Gets the local anonymous user ID, creating one if it doesn't exist yet."""
    device_file = ".device_id"
    # Check if we already created a device ID file before
    if os.path.exists(device_file):
        with open(device_file, "r") as f:
            return f.read().strip()
    else:
        # If no file exists, generate a brand new random unique ID
        new_id = str(uuid.uuid4())
        with open(device_file, "w") as f:
            f.write(new_id)
        return new_id

def save_submission(code_content: str, category: str = "Uncategorized"):
    """Saves a valid code submission to Supabase."""
    #1. Grab our unique local device ID
    user_id = get_or_create_user_id()

    try:
        # 2. Insert a new row into the 'submissions' table in Supabase
        response= supabase.table("submissions").insert({
            "user_id": user_id,
            "code_content": code_content,
            "category": category
        }).execute()
        existing = supabase.table("category_stats").select("*").eq("category_name", category).execute()
        if existing.data:
            current_count = existing.data[0]["count"]
            supabase.table("category_stats").update({"count": current_count + 1}).eq("category_name", category).execute()
        else:
            supabase.table("category_stats").insert({"category_name": category, "count": 1}).execute()
    except Exception as e:
        print(f"Error saving to database: {e}")

def fetch_category_statistics():
    """Fetches category stats from Supabase and displays top 3 categories by popularity."""
    try:
        response=supabase.table("category_stats").select("*").execute()
        stats_data= response.data
        if not stats_data:
            print("No statistics found yet. Submit some code snippets first!")
            return
        total_submissions = sum(item["count"] for item in stats_data)
        sorted_stats = sorted(stats_data, key=lambda x: x["count"], reverse=True)
        top_3=sorted_stats[:3]
        print(f"Total Submissions Tracked: {total_submissions}\n")
        print("--- Top 3 Most Popular Categories ---")
        for rank, item in enumerate(top_3, start=1):
            category_name = item["category_name"]
            count = item["count"]
            percentage = (count / total_submissions) * 100
            print(f"{rank}. {category_name}")
            print(f"   - Submissions: {count}")
            print(f"   - Share: {percentage:.2f}%\n")
    except Exception as e:
        print(f"Error fetching statistics: {e}")

def get_existing_categories() -> list[str]:
    """Returns a list of all existing category names from category_stats."""
    try:
        response=supabase.table("category_stats").select("category_name").execute()
        #return a simple list of category names
        return [row["category_name"] for row in response.data if row["category_name"] != "Uncategorized"]
    except Exception as e:
        print(f"Warning: Could not fetch existing categories: {e}")
        return[]
