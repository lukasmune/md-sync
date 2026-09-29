import re
from urllib.parse import urljoin

import requests


GIFA_URL = (
    "https://www.gifa.com/en/exhibitors-products/"
    "exhibitor-product-search/"
)


def test_gifa_is_reachable():
    response = requests.get(
        GIFA_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    assert response.status_code == 200


def test_gifa_response_contains_data():
    response = requests.get(
        GIFA_URL,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    assert response.status_code == 200
    assert len(response.text) > 0

    print("\n--- RESPONSE HEAD ---")
    print(response.text[:2000])
    print("--- RESPONSE HEAD END ---")

    print("\nContent-Type:", response.headers.get("Content-Type"))

    from urllib.parse import urljoin

import requests


GIFA_URL = (
    "https://www.gifa.com/en/exhibitors-products/"
    "exhibitor-product-search/"
)

GIFA_BASE_URL = "https://www.gifa.com"


def get_gifa_headers():
    return {
        "User-Agent": "Mozilla/5.0"
    }


def test_gifa_is_reachable():
    response = requests.get(
        GIFA_URL,
        timeout=30,
        headers=get_gifa_headers()
    )

    assert response.status_code == 200


def test_gifa_response_contains_data():
    response = requests.get(
        GIFA_URL,
        timeout=30,
        headers=get_gifa_headers()
    )

    assert response.status_code == 200
    assert len(response.text) > 0

    print("\n--- RESPONSE HEAD ---")
    print(response.text[:2000])
    print("--- RESPONSE HEAD END ---")

    print("\nContent-Type:", response.headers.get("Content-Type"))


def test_registry_application_assets_are_reachable():
    response = requests.get(
        GIFA_URL,
        timeout=30,
        headers=get_gifa_headers()
    )

    assert response.status_code == 200

    html = response.text

    script_paths = re.findall(
        r'<script[^>]+src=["\']([^"\']+\.js)',
        html,
    )

    assert "/build/runtime." in html
    assert "/build/app." in html

    for script_path in script_paths:
        script_response = requests.get(
            urljoin(GIFA_BASE_URL, script_path),
            timeout=30,
            headers=get_gifa_headers(),
        )
        assert script_response.status_code == 200


def test_registry_links_use_current_vis_taxonomy():
    route_urls = [
        "https://www.gifa.com/en/vis/v1/directory/a",
        "https://www.gifa.com/en/vis/v1/search?_query=",
        "https://www.gifa.com/en/vis/v1/exhprofiles/a22bioOWRFK8LBNtqXs6Cw",
    ]

    for route_url in route_urls:
        response = requests.get(
            route_url,
            timeout=30,
            headers=get_gifa_headers(),
        )
        assert response.status_code == 200