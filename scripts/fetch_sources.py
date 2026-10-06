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


def save_json_records(source: str, records: dict[str, object]) -> int:
    if not records:
        raise ValueError(f"{source} response contained no substance records")

    source_root = ROOT / "archive" / source
    source_root.mkdir(parents=True, exist_ok=True)
    expected = {source_root / f"{name}.json" for name in records}
    for old_file in source_root.glob("*.json"):
        if old_file not in expected:
            old_file.unlink()

    changed = 0
    for name, record in records.items():
        content = (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        changed += save(source, f"{name}.json", content)
    return changed


def substance_filename(value: str) -> str:
    filename = urllib.parse.quote(value.strip(), safe="-_.()")
    if not filename or filename in {".", ".."}:
        raise ValueError(f"invalid substance filename: {value!r}")
    return filename


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
    for source, url, data, content_type in [
        ("psychonautwiki", "https://api.psychonautwiki.org/",
         json.dumps({"query": pw_query}).encode("utf-8"), "application/json"),
        ("tripsit", "https://raw.githubusercontent.com/TripSit/drugs/main/drugs.json", None, None),
    ]:
        try:
            payload = request(url, data=data, content_type=content_type)
            response = json.loads(payload)
            if source == "psychonautwiki":
                if response.get("errors"):
                    raise ValueError("GraphQL returned errors")
                substances = response.get("data", {}).get("substances")
                if not isinstance(substances, list):
                    raise ValueError("GraphQL response contained no substances list")
                records = {
                    substance_filename(record["name"]): record
                    for record in substances
                    if isinstance(record, dict) and isinstance(record.get("name"), str)
                }
            else:
                if not isinstance(response, dict):
                    raise ValueError("TripSit response was not a substance mapping")
                records = {
                    substance_filename(name): record
                    for name, record in response.items()
                    if isinstance(name, str) and isinstance(record, dict)
                }
            changed = save_json_records(source, records)
            print(f"{source}: {len(records)} substances, {changed} changed")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as error:
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
        response = json.loads(request(endpoint))
        bindings = response.get("results", {}).get("bindings")
        if not isinstance(bindings, list):
            raise ValueError("Wikidata response contained no bindings list")
        records: dict[str, dict[str, object]] = {}
        for binding in bindings:
            entity = binding.get("item", {}).get("value", "")
            qid = entity.rsplit("/", 1)[-1]
            if not qid:
                raise ValueError("Wikidata binding had no item identifier")
            records.setdefault(qid, {"item": entity, "bindings": []})["bindings"].append(binding)
        changed = save_json_records("wikidata", records)
        print(f"wikidata: {len(records)} substances, {changed} changed")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError, KeyError) as error:
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
