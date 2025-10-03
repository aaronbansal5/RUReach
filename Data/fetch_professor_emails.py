import requests
import os 
from dotenv import load_dotenv

load_dotenv()

HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")

# Don't use this script too often, as it may hit rate limits on the Hunter.io API we only have 50 emails
def get_email(full_name, domain=None):
    url = "https://api.hunter.io/v2/email-finder"
    params = {"api_key": HUNTER_API_KEY, "full_name": full_name}
    if domain:
        params["domain"] = domain

    response = requests.get(url, params=params)
    if response.status_code == 200:
        return response.json().get("data", {}).get("email")
    else:
        print(f"Error: {response.status_code} {response.text}")
        return None
    
if __name__ == "__main__":
    email = get_email("David Menendez", "rutgers.edu")
    print(email)