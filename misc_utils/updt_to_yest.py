import os
from notion_client import Client
from datetime import datetime, timedelta
import json
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load environment variables
NOTION_KEY = os.getenv('NOTION_KEY')
NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')

# Define Pakistan timezone
PKT = ZoneInfo("Asia/Karachi")

# Get current time in Pakistan
now_pkt = datetime.now(PKT)
yesterday_pkt = (now_pkt - timedelta(days=1)).strftime("%Y-%m-%d")
today_pkt = now_pkt.strftime("%Y-%m-%d")

# Initialize the Notion client
notion = Client(auth=NOTION_KEY)

def get_pages_for_date(database_id, property_name, target_date):
    start_of_day = datetime.strptime(target_date, "%Y-%m-%d")
    end_of_day = start_of_day + timedelta(days=1)
    filter_obj = {
        "property": property_name,
        "date": {
            "on_or_after": start_of_day.strftime("%Y-%m-%d"),
            "before": end_of_day.strftime("%Y-%m-%d")
        }
    }
    response = notion.databases.query(
        database_id=database_id,
        filter=filter_obj
    )
    return response['results']

def update_page_date(page_id, property_name, new_start, new_end=None):
    properties = {
        property_name: {
            "date": {
                "start": new_start
            }
        }
    }
    if new_end:
        properties[property_name]["date"]["end"] = new_end
    response = notion.pages.update(page_id=page_id, properties=properties)
    return response

def shift_date_preserving_time(dt_str, new_date):
    dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
    y, m, d = map(int, new_date.split('-'))
    return dt.replace(year=y, month=m, day=d).isoformat()

if __name__ == "__main__":
    property_name = "Date-Time"
    yesterday = yesterday_pkt
    today = today_pkt

    # Query all pages with a date for yesterday
    pages = get_pages_for_date(NOTION_DATABASE_ID, property_name, yesterday)
    print(f"Found {len(pages)} pages for yesterday ({yesterday})")

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
    # backup_filename = f"notion_backup_{yesterday}_to_{today}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    # backup_path = os.path.join(backup_dir, backup_filename)
    # with open(backup_path, 'w') as f:
    #     json.dump(backup_data, f, indent=2)
    # print(f"Backup of {len(backup_data)} pages saved to {backup_path}")

    # Now update the pages
    for page in pages:
        date_prop = page['properties'].get(property_name, {})
        date_val = date_prop.get('date', {})
        orig_start = date_val.get('start')
        orig_end = date_val.get('end')
        if not orig_start:
            print(f"Skipping page {page['id']} (no start time)")
            continue
        new_start = shift_date_preserving_time(orig_start, today)
        new_end = shift_date_preserving_time(orig_end, today) if orig_end else None
        print(f"Updating page {page['id']} from start: {orig_start} to {new_start}, end: {orig_end} to {new_end}")
        update_page_date(page['id'], property_name, new_start, new_end)
