import os
from notion_client import Client
from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
# In GitHub Actions, environment variables are already set via secrets
# load_dotenv() will only load if .env exists and won't override existing env vars
load_dotenv()

# Load environment variables (works for both local .env and GitHub Actions secrets)
NOTION_KEY = os.getenv("NOTION_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Validate that required environment variables are set
if not NOTION_KEY:
    raise ValueError("NOTION_KEY environment variable is not set")
if not NOTION_DATABASE_ID:
    raise ValueError("NOTION_DATABASE_ID environment variable is not set")

# Define Pakistan timezone
PKT = ZoneInfo("Asia/Karachi")

# Get current time in Pakistan (works correctly regardless of server location)
now_pkt = datetime.now(PKT)
today_pkt = now_pkt.strftime("%Y-%m-%d")
one_month_ago_pkt = (now_pkt - timedelta(days=30)).strftime("%Y-%m-%d")

# Initialize the Notion client
notion = Client(auth=NOTION_KEY)


def get_pages_from_past_month(database_id, property_name, today_date, cutoff_date):
    """Get all pages with dates from the past month (before today, on or after cutoff)"""
    filter_obj = {
        "and": [
            {"property": property_name, "date": {"before": today_date}},
            {"property": property_name, "date": {"on_or_after": cutoff_date}},
        ]
    }
    # In notion-client 2.7.0+, databases use data_sources.query()
    # Try data_sources first (new API), fallback to databases (old API)
    try:
        response = notion.data_sources.query(data_source_id=database_id, filter=filter_obj)
    except (AttributeError, Exception):
        # Fallback for older API versions that use databases.query
        try:
            response = notion.databases.query(database_id=database_id, filter=filter_obj)
        except AttributeError:
            # Last resort for very old versions
            response = notion.databases.query(**{"database_id": database_id, "filter": filter_obj})
    return response["results"]


def update_page_date(page_id, property_name, new_start, new_end=None):
    properties = {property_name: {"date": {"start": new_start}}}
    if new_end:
        properties[property_name]["date"]["end"] = new_end
    response = notion.pages.update(page_id=page_id, properties=properties)
    return response


def shift_date_preserving_time(dt_str, new_date):
    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    y, m, d = map(int, new_date.split("-"))
    return dt.replace(year=y, month=m, day=d).isoformat()


if __name__ == "__main__":
    property_name = "Date-Time"
    today = today_pkt
    one_month_ago = one_month_ago_pkt

    print(f"Current time in Pakistan: {now_pkt}")
    print(f"Today's date (Pakistan): {today}")
    print(f"Looking for events from {one_month_ago} to yesterday")

    # Query all pages with dates from the past month (before today)
    pages = get_pages_from_past_month(
        NOTION_DATABASE_ID, property_name, today, one_month_ago
    )
    print(f"Found {len(pages)} pages from the past month (before {today})")

    # Backup the current state before updating
    # backup_data = []
    # for page in pages:
    #     date_prop = page['properties'].get(property_name, {})
    #     date_val = date_prop.get('date', {})
    #     backup_data.append({
    #         'page_id': page['id'],
    #         'start': date_val.get('start'),
    #         'end': date_val.get('end'),
    #         'time_zone': date_val.get('time_zone')
    #     })
    # backup_dir = "notion_backups"
    # os.makedirs(backup_dir, exist_ok=True)
    # backup_filename = f"notion_backup_{one_month_ago}_to_{today}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    # backup_path = os.path.join(backup_dir, backup_filename)
    # with open(backup_path, 'w') as f:
    #     json.dump(backup_data, f, indent=2)
    # print(f"Backup of {len(backup_data)} pages saved to {backup_path}")

    # Now update the pages to today
    updated_count = 0
    for page in pages:
        date_prop = page["properties"].get(property_name, {})
        date_val = date_prop.get("date", {})
        orig_start = date_val.get("start")
        orig_end = date_val.get("end")
        if not orig_start:
            print(f"Skipping page {page['id']} (no start time)")
            continue
        new_start = shift_date_preserving_time(orig_start, today)
        new_end = shift_date_preserving_time(orig_end, today) if orig_end else None
        print(f"Updating page {page['id']} from start: {orig_start} to {new_start}")
        update_page_date(page["id"], property_name, new_start, new_end)
        updated_count += 1

    print(f"Successfully updated {updated_count} pages to today ({today})")
