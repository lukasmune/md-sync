import requests


BASE_URL = "https://widgets.messe-duesseldorf.de/vis-api/vis/v1"


def test_directory_api():
    url = f"{BASE_URL}/en/directory/a"

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
            "X-Vis-Domain": "www.gifa.com",
        },
        timeout=30,
    )

    print("\n--- DIRECTORY API ---")
    print("Request URL:", response.request.url)
    print("Request headers:")

    for key, value in response.request.headers.items():
        print(f"  {key}: {value}")

    print("\nResponse:")
    print("Status:", response.status_code)
    print("Content-Type:", response.headers.get("Content-Type"))
    print(response.text[:1000])

    print("--- END DIRECTORY API ---")

    assert response.status_code == 200