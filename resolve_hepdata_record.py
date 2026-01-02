import requests

BASE = "https://www.hepdata.net"

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "mdl-basin-test/0.1"
}

def get_json(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} for {url}")
    if "application/json" not in r.headers.get("Content-Type", ""):
        raise RuntimeError(
            f"Non-JSON response from {url}\n"
            f"Content-Type: {r.headers.get('Content-Type')}\n"
            f"Preview: {r.text[:200]}"
        )
    return r.json()

def search_records(query, max_hits=50):
    data = get_json(f"{BASE}/search/", params={"q": query, "size": max_hits})
    return extract_records(data)


def extract_records(data):
    # HEPData search schema varies; handle known shapes.
    if "records" in data:
        return data["records"]
    if "results" in data:
        return data["results"]
    hits = data.get("hits")
    if isinstance(hits, dict) and "hits" in hits:
        return hits["hits"]
    raise RuntimeError(f"Unknown HEPData search schema. Keys: {list(data.keys())}")

def filter_hits(hits):
    keep = []
    for h in hits:
        meta = h.get("metadata", h)
        title = meta.get("title", "").lower()
        collab = meta.get("collaboration", "")
        year = meta.get("date_published", "")[:4]

        if collab != "CMS":
            continue
        if year < "2022":
            continue
        if "13.6" not in title:
            continue
        if not ("diphoton" in title or "γγ" in title):
            continue
        if "differential" not in title:
            continue

        keep.append(h)
    return keep

def main():
    hits = search_records("H γγ 13.6 TeV CMS differential")
    filtered = filter_hits(hits)

    print(f"Found {len(filtered)} candidate records\n")

    for h in filtered:
        meta = h["metadata"]
        print("ID:", h["id"])
        print("Title:", meta.get("title"))
        print("Published:", meta.get("date_published"))
        print("URL:", f"{BASE}/record/{h['id']}")
        print("-" * 60)

if __name__ == "__main__":
    main()
