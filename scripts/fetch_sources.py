#!/usr/bin/env python3
"""Save upstream source responses as separately reviewable snapshots."""

from __future__ import annotations

import concurrent.futures
import json
import os
import pathlib
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
USER_AGENT = "SubstancesArchive/1.0 (+https://github.com/)"


def request(
    url: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    cookie: str | None = None,
) -> bytes:
    headers = {"User-Agent": USER_AGENT}
    if content_type:
        headers["Content-Type"] = content_type
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as response:
        return response.read()


def save(source: str, filename: str, content: bytes) -> bool:
    destination = ROOT / "archive" / source / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.read_bytes() == content:
        return False
    destination.write_bytes(content)
    print(f"updated {destination.relative_to(ROOT)} ({len(content)} bytes)")
    return True


def fetch_freeodwiki() -> None:
    tree_url = "https://api.github.com/repos/SalviaSWC/FreeODwiki/git/trees/main?recursive=1"
    tree = json.loads(request(tree_url))
    paths = [
        entry["path"] for entry in tree["tree"]
        if entry.get("type") == "blob"
        and (entry["path"].startswith("药物/") and entry["path"].endswith(".md")
             or entry["path"] in {"LICENSE", "README.md", "index.md"})
    ]
    if not paths:
        raise ValueError("FreeODwiki tree contained no expected source files")

    def fetch(path: str) -> tuple[str, bytes]:
        url = "https://raw.githubusercontent.com/SalviaSWC/FreeODwiki/main/" + urllib.parse.quote(path)
        return path, request(url)

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        fetched = dict(pool.map(fetch, paths))
    source_root = ROOT / "archive" / "freeodwiki"
    expected = {source_root / path for path in fetched}
    if source_root.exists():
        for old_file in source_root.rglob("*"):
            if old_file.is_file() and old_file not in expected:
                old_file.unlink()
        for old_dir in sorted((p for p in source_root.rglob("*") if p.is_dir()), reverse=True):
            try:
                old_dir.rmdir()
            except OSError:
                pass
    changed = sum(save("freeodwiki", path, content) for path, content in fetched.items())
    print(f"FreeODwiki: {len(paths)} original files, {changed} changed")


def main() -> None:
    failures: list[str] = []

    # Preserve the complete GraphQL response; no field mapping or normalization.
    pw_query = """
    {
      substances(limit: 500, offset: 0) {
        name url featured systematicName commonNames
        class { chemical psychoactive }
        tolerance { full half zero }
        crossTolerances toxicity addictionPotential
        dangerousInteractions { name }
        unsafeInteractions { name }
        uncertainInteractions { name }
        roas {
          name
          dose { units threshold heavy light { min max } common { min max } strong { min max } }
          duration { onset { min max units } comeup { min max units } peak { min max units }
                     offset { min max units } total { min max units } afterglow { min max units } }
          bioavailability { min max }
        }
      }
    }
    """
    sources = [
        ("psychonautwiki", "response.json", "https://api.psychonautwiki.org/",
         json.dumps({"query": pw_query}).encode("utf-8"), "application/json"),
        ("tripsit", "drugs.json", "https://raw.githubusercontent.com/TripSit/drugs/main/drugs.json", None, None),
    ]
    for source, filename, url, data, content_type in sources:
        try:
            payload = request(url, data=data, content_type=content_type)
            if source == "psychonautwiki" and json.loads(payload).get("errors"):
                raise ValueError("GraphQL returned errors")
            save(source, filename, payload)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
            failures.append(f"{source}: {error}")
            print(f"FAILED {source}: {error}")

    try:
        fetch_freeodwiki()
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        failures.append(f"freeodwiki: {error}")
        print(f"FAILED freeodwiki: {error}")

    query = "SELECT ?item ?itemLabel ?atc WHERE { ?item wdt:P267 ?atc . SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". } } ORDER BY ?item ?atc"
    endpoint = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode(
        {"query": query, "format": "json"}
    )
    try:
        save("wikidata", "atc-medicines.json", request(endpoint))
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        failures.append(f"wikidata: {error}")
        print(f"FAILED wikidata: {error}")

    euda_url = "https://www.euda.europa.eu/publications/european-drug-report_en"
    try:
        save("euda", "european-drug-report.html", request(
            euda_url, cookie=os.environ.get("EUDA_COOKIE")
        ))
    except urllib.error.HTTPError as error:
        if error.code == 403:
            print("UNAVAILABLE euda: EUDA returned HTTP 403 (Cloudflare); set EUDA_COOKIE to a valid session cookie")
        else:
            failures.append(f"euda: {error}")
            print(f"FAILED euda: {error}")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        failures.append(f"euda: {error}")
        print(f"FAILED euda: {error}")

    if failures:
        raise SystemExit("Source fetch failures: " + "; ".join(failures))


if __name__ == "__main__":
    main()
