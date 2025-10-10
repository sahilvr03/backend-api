import pytz
import datetime
from pymongo import MongoClient
from timezonefinder import TimezoneFinder
import pycountry

# MongoDB connection
client = MongoClient("mongodb+srv://vijay:baby9271@internsportal.oswhrxp.mongodb.net/?retryWrites=true&w=majority&appName=internsPortal")
db = client["lead_dbb"]
collection = db["leadss"]

tf = TimezoneFinder()

def get_timezone_from_country(country_name: str):
    """Get timezone string from country name"""
    try:
        country = pycountry.countries.lookup(country_name)
        # Take the first timezone
        tz_name = pytz.country_timezones[country.alpha_2][0]
        return tz_name
    except Exception as e:
        print(f"❌ Could not map timezone for {country_name}: {e}")
        return "UTC"

def schedule_emails():
    """Assign due_time for each lead"""
    leads = collection.find({"due_time": {"$exists": False}})
    for lead in leads:
        country = lead.get("country", "United States")
        tz_name = get_timezone_from_country(country)
        tz = pytz.timezone(tz_name)

        now_local = datetime.datetime.now(tz)
        target_time = tz.localize(datetime.datetime(now_local.year, now_local.month, now_local.day, 9, 0))

        if now_local >= target_time:
            target_time += datetime.timedelta(days=1)

        collection.update_one(
            {"_id": lead["_id"]},
            {"$set": {
                "due_time": target_time,
                "timezone": tz_name,
                "status": "scheduled"
            }}
        )
        print(f"📌 Lead {lead['email']} scheduled for {target_time} ({tz_name})")

if __name__ == "__main__":
    schedule_emails()
