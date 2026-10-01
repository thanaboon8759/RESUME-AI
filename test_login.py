import os
from dotenv import load_dotenv

load_dotenv("d:/MyProject/backend/.env")

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
supabase = create_client(url, key)

email = "admin@example.com"
password = "REDACTED"

try:
    res = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    print(f"Login successful: session created!")
    
    supabase.auth.update_user({
        "data": {
            "role": "admin"
        }
    })
    print("User metadata updated to role: admin")
except Exception as e:
    print(f"Login failed: {e}")
