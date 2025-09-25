

import os
import json
import requests

API_URL = "https://api.apollo.io/api/v1/people/match"

def get_api_key():
    key = "oonqrVtMGwBkasJeoOnVzw"
    if key:
        return key.strip()
    # fallback: prompt user
    return input("Enter your Apollo API key: ").strip()

def build_headers(api_key):
    # Apollo docs say include key in header. Different examples show Bearer or X-Api-Key.
    # We include both; remove one if your key format requires a specific header.
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "X-Api-Key": api_key,
    }

def find_person(first_name, last_name, domain, reveal_personal_emails=True):
    api_key = get_api_key()
    headers = build_headers(api_key)

    payload = {
        "first_name": first_name,
        "last_name": last_name,
        # commonly used param names: company_domain or domain; try both if needed.
        "company_domain": domain,
        # reveal personal emails consumes credits and may not be available on free plan:
        "reveal_personal_emails": bool(reveal_personal_emails)
    }

    try:
        resp = requests.post(API_URL, headers=headers, json=payload, timeout=15)
    except Exception as e:
        print("Request failed:", e)
        return

    if resp.status_code == 200:
        data = resp.json()
        # pretty print some useful fields if present
        print("\nRaw response (truncated):")
        print(json.dumps(data, indent=2)[:4000])  # avoid dumping too large
        print("\n--- Parsed / handy fields ---")
        # attempt to extract likely fields
        person = data.get("person") or data.get("matched_person") or data.get("data")
        if not person:
            # try common response shapes
            person = data

        # try a few frequent keys
        email = person.get("email") if isinstance(person, dict) else None
        work_email = person.get("work_email") if isinstance(person, dict) else None
        company = person.get("company") if isinstance(person, dict) else None
        title = person.get("title") if isinstance(person, dict) else person.get("job_title") if isinstance(person, dict) else None

        # fallback: search whole JSON for any email-like strings (simple)
        if not email:
            import re
            all_text = json.dumps(data)
            matches = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", all_text)
            email = matches[0] if matches else None

        print(f"Name: {first_name} {last_name}")
        if title:
            print("Title:", title)
        if company:
            # company may be object or string
            if isinstance(company, dict):
                print("Company:", company.get("name") or company.get("domain"))
            else:
                print("Company:", company)
        print("Email (best guess):", email or work_email or "Not found / not revealed")
        # print full JSON if user wants
        if not (email or work_email):
            print("\nNote: email not found in response — either Apollo couldn't match, or your API key/plan doesn't allow reveals.")
    else:
        print(f"API returned status {resp.status_code}")
        try:
            print(resp.json())
        except Exception:
            print(resp.text)

def main():
    print("Apollo Email Finder — small terminal utility")
    first = input("First name: ").strip()
    last = input("Last name: ").strip()
    domain = input("Company domain (example.com): ").strip()
    reveal = input("Reveal personal emails? (y/N): ").strip().lower() == "y"

    find_person(first, last, domain, reveal_personal_emails=reveal)

if __name__ == "__main__":
    main()
