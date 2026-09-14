import os
import sys
from dotenv import load_dotenv

load_dotenv("d:/MyProject/backend/.env")

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") # This seems to actually be the anon key in this project

if not url or not key:
    print("Error: Missing Supabase credentials")
    sys.exit(1)

supabase = create_client(url, key)

email = "admin@example.com"
password = "REDACTED"

print(f"Signing up user {email}...")
try:
    res = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": {
                "role": "admin"
            }
        }
    })
    print(f"Signup successful: {res}")
except Exception as e:
    print(f"Signup error (maybe user already exists?): {e}")

    print("Attempting to login...")
    try:
        res = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        print("Login successful! Updating user metadata...")
        res = supabase.auth.update_user({
            "data": {
                "role": "admin"
            }
        })
        print("Metadata updated.")
    except Exception as e2:
        print(f"Login/update failed: {e2}")
