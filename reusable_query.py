import argparse
import sys
import requests

BASE = "https://www.hepdata.net"
HEADERS = {
    "Accept": "application/json",
    "User-Agent": "dashiq-hepdata-debug/0.1",
}


def get_json(url, params=None):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    if "application/json" not in resp.headers.get("Content-Type", ""):
        snippet = resp.text[:200].replace("\n", " ").strip()
        raise RuntimeError(
            f"Non-JSON response from {url} "
            f"(content-type={resp.headers.get('Content-Type')!r}): {snippet!r}"
        )
    return resp.json()


def extract_records(data):
    if "records" in data:
        return data["records"]
    if "results" in data:
        return data["results"]
    hits = data.get("hits")
    if isinstance(hits, dict) and "hits" in hits:
        return hits["hits"]
    raise RuntimeError(f"Unknown search schema. Keys: {list(data.keys())}")


def search_records(query, size):
    data = get_json(f"{BASE}/search/", params={"q": query, "size": size})
    return extract_records(data)


def record_id(record):
    return record.get("id") or record.get("record_id")


def record_meta(record):
    return record.get("metadata", record)


def list_records(query, size, filters):
    records = search_records(query, size)
    if filters:
        fset = [f.lower() for f in filters]
        def keep_record(r):
            meta = record_meta(r)
            title = (meta.get("title") or "").lower()
            return all(f in title for f in fset)
        records = [r for r in records if keep_record(r)]
    print(f"Found {len(records)} records for query: {query!r}")
    for r in records:
        meta = record_meta(r)
        rid = record_id(r)
        title = meta.get("title")
        collab = meta.get("collaboration")
        date = meta.get("date_published")
        print(f"- id={rid} | collab={collab} | date={date} | title={title}")


def show_tables(record):
    url = f"{BASE}/record/{record}?format=json"
    data = get_json(url)
    meta = data.get("metadata", {})
    title = meta.get("title") or data.get("title")
    print(f"Record {record}: {title}")
    print(f"Top-level keys: {list(data.keys())}")
    tables = data.get("tables")
    if tables is None:
        tables = data.get("data_tables")
    if tables is None:
        tables = []
    print(f"Record {record} has {len(tables)} tables")
    for i, t in enumerate(tables):
        title = t.get("title") or t.get("name")
        location = t.get("location") or t.get("url")
        desc = (t.get("description") or "").strip()
        data_json = None
        data = t.get("data", {})
        if isinstance(data, dict):
            data_json = data.get("json")
        print(f"- index={i} | title={title} | location={location}")
        if desc:
            print(f"  desc: {desc}")
        if data_json:
            print(f"  json: {data_json}")
        text = " ".join(
            [str(title or ""), str(desc or ""), str(location or "")]
        ).lower()
        if any(k in text for k in ["corr", "correlation", "cov", "covariance"]):
            print("  -> candidate correlation/covariance table")
        if any(k in text for k in ["theory", "prediction", "nnlo", "sm "]):
            print("  -> candidate theory/prediction table")

    # Scan record-level resources for covariance hints.
    resources = data.get("record", {}).get("files") or data.get("record", {}).get("resources")
    if resources:
        print("Record resources:")
        for r in resources:
            name = (r.get("key") or r.get("name") or "").lower()
            url = r.get("url") or r.get("link")
            print(f"- {name} | {url}")
            if any(k in name for k in ["corr", "correlation", "cov", "covariance"]):
                print("  -> candidate correlation/covariance resource")
        if "links" in first:
            print("First table links:", first["links"])


def show_table(record, table_index):
    url = f"{BASE}/record/{record}?format=json"
    data = get_json(url)
    tables = data.get("tables")
    if tables is None:
        tables = data.get("data_tables", [])
    try:
        table = tables[table_index]
    except IndexError as exc:
        raise RuntimeError(
            f"Table index {table_index} out of range (0..{len(tables)-1})"
        ) from exc
    table_url = None
    data_block = table.get("data", {})
    if isinstance(data_block, dict):
        table_url = data_block.get("json")
    if table_url is None and "location" in table:
        table_url = BASE + table["location"] + "?format=json"
    if table_url is None:
        raise RuntimeError(f"No JSON URL found for table index {table_index}")
    table_data = get_json(table_url)
    print(f"Table {table_index} title: {table.get('title') or table.get('name')}")
    print(f"Table {table_index} location: {table.get('location')}")
    print(f"Table {table_index} json: {table_url}")
    print(f"Keys: {list(table_data.keys())}")
    desc = table_data.get("description") or table.get("description")
    if desc:
        print(f"Description: {desc}")
    headers = table_data.get("headers")
    if headers:
        print(f"Headers: {headers}")
    qualifiers = table_data.get("qualifiers")
    if qualifiers:
        print(f"Qualifiers: {qualifiers}")
    related_tables = table_data.get("related_tables")
    if related_tables:
        print(f"Related tables: {related_tables}")
    related_to_this = table_data.get("related_to_this")
    if related_to_this:
        print(f"Related to this: {related_to_this}")
    assoc = table_data.get("associated_files")
    if assoc:
        print(f"Associated files: {assoc}")
    resources = table_data.get("resources")
    if resources:
        print(f"Resources: {resources}")
    print(f"Values length: {len(table_data.get('values', []))}")
    values = table_data.get("values", [])
    if values:
        print(f"First value: {values[0]}")


def parse_args(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--query", help="Search query for HEPData")
    p.add_argument("--size", type=int, default=50, help="Max results to return")
    p.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Case-insensitive substring filter applied to titles; can repeat",
    )
    p.add_argument("--record", help="HEPData record id (e.g. ins1234567)")
    p.add_argument("--tables", action="store_true", help="List tables in record")
    p.add_argument("--table", type=int, help="Show details for one table index")
    return p.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    if args.query:
        list_records(args.query, args.size, args.filter)
        return 0

    # Default action: run a targeted search without requiring args.
    # Default: search for ATLAS 139 fb-1 Higgs differential records.
    # Default: scan tables for correlation/covariance and theory/prediction hints.
    default_record = "137886"
    show_tables(default_record)
    return 0

    if args.record and args.tables:
        show_tables(args.record)
        return 0

    if args.record is not None and args.table is not None:
        show_table(args.record, args.table)
        return 0

    print("No action requested. Use --query or --record with --tables/--table.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
