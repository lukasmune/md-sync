import requests


BASE_URL = "https://widgets.messe-duesseldorf.de/vis-api/vis/v1"


def test_directory_api():
    url = f"{BASE_URL}/en/directory/a"

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "X-Vis-Domain": "www.gifa.com",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=30,
    )

    print("\n--- DIRECTORY API ---")
    print("URL:", response.url)
    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print("Response:")
    print(response.text[:10000])
    print("--- END DIRECTORY API ---")

    assert response.status_code == 200