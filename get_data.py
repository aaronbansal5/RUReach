import requests

# Define the base URL for the OpenAlex API
base_url = "https://api.openalex.org"

# Define the ROR ID for Rutgers University
rutgers_ror_id = "https://ror.org/02v8g7k65"

# Function to fetch authors affiliated with Rutgers
def fetch_rutgers_authors(ror_id):
    authors = []
    page = 1
    while True:
        # Construct the API endpoint
        endpoint = f"{base_url}/authors?filter=affiliations.institution.id:{ror_id}&page={page}"
        response = requests.get(endpoint)
        data = response.json()

        # Check if there are no more authors
        if not data['meta']['next_page']:
            break

        # Add authors to the list
        authors.extend(data['data'])
        page += 1

    return authors

# Function to fetch works (publications) by an author
def fetch_author_works(author_id):
    works = []
    page = 1
    while True:
        # Construct the API endpoint
        endpoint = f"{base_url}/works?filter=authorships.author.id:{author_id}&page={page}"
        response = requests.get(endpoint)
        data = response.json()

        # Check if there are no more works
        if not data['meta']['next_page']:
            break

        # Add works to the list
        works.extend(data['data'])
        page += 1

    return works

# Fetch authors affiliated with Rutgers
authors = fetch_rutgers_authors(rutgers_ror_id)

# Filter authors to include only those with 'faculty' role
faculty_authors = [author for author in authors if 'faculty' in [affiliation['role'] for affiliation in author['authorships']]]

# For each faculty author, fetch their works
for author in faculty_authors:
    author_id = author['id']
    works = fetch_author_works(author_id)
    print(f"Author: {author['display_name']}")
    print(f"Affiliation: {author['affiliations'][0]['institution']['display_name']}")
    print("Works:")
    for work in works:
        print(f"  - Title: {work['title']}")
        print(f"    DOI: {work.get('doi', 'N/A')}")
    print("\n")
