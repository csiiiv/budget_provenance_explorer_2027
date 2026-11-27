"""Build PAP-level risk tables from the published DPWH chain snapshot.

House project leaves only. Senate amounts use the linked amendment or the
House amount if Annex A-4 contains no linked amendment. Unlinked Senate
rows and control nodes are excluded and disclosed separately.
"""
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "web/public/data"
BUCKETS = ("none", "partial", "complete", "unchecked")

def metric():
    return {"house_count": 0, "house_php": 0, "senate_count": 0, "senate_php": 0}

def add(m, house, senate):
    m["house_count"] += 1
    m["house_php"] += house
    m["senate_count"] += int(senate > 0)
    m["senate_php"] += senate

def group(program, pap):
    return {"program": program, "pap": pap, "total": metric(),
            "documents": {k: metric() for k in BUCKETS},
            "flagged": metric(), "flags": defaultdict(metric),
            "families": defaultdict(metric)}

def office_group(h):
    region = " ".join((h.get("region_key") or h.get("region") or "Unspecified region").split())
    office = " ".join((h.get("office") or "Unspecified implementing office").split())
    label = office.casefold()
    if re.search(r"district (?:engineering )?office|\bdeo\b", label):
        kind = "District engineering office"
    elif "regional office" in label:
        kind = "Regional office"
    elif "central office" in label or "bureau proper" in label:
        kind = "Central / bureau office"
    elif label == "unspecified implementing office":
        kind = "Unspecified office"
    else:
        kind = "Other implementing office"
    return region, office, kind

def project_record(c):
    h, s = c.get("house"), c.get("senate")
    if not h or h.get("allocation_kind") == "control":
        return None
    review = c.get("review") or {}
    n = review.get("key_documents_found")
    bucket = "none" if n == 0 else "partial" if n in (1, 2, 3, 4) else "complete" if n == 5 else "unchecked"
    flags = sorted({(f[0], f[1]) for f in c.get("flags", [])})
    region, office, kind = office_group(h)
    return {
        "id": c["id"], "title": h.get("title"),
        "program": h.get("program") or "Unclassified program",
        "pap": h.get("pap") or "No separate PAP heading",
        "region": region, "office": office, "office_type": kind,
        "house_php": h["amount_php"], "senate_php": (s.get("sv_php") or 0) if s else h["amount_php"],
        "senate_title": s.get("senate_title") if s else None,
        "senate_action": (c.get("actions") or {}).get("house_senate") if s else "Carried forward (unlisted)",
        "house_page": h.get("pdf_page"), "senate_page": s.get("pdf_page") if s else None,
        "bucket": bucket, "key_documents_found": n,
        "documents": {k: review.get(k) for k in ("has_pow", "has_bp202", "has_development_council", "has_geotagged_photos", "has_certificate_of_implementability")},
        "flags": [code for code, _ in flags],
        "families": sorted({family for _, family in flags}),
        "flagged": bool(flags or (review.get("red_flags") or 0) > 0),
        "hgab_id": review.get("hgab_id"),
        "project_page": review.get("project_page"), "reviewer_page": review.get("reviewer_page"),
    }

def build(bundle, grouping="pap"):
    groups = {}
    total = group("All regions", "All offices") if grouping == "office" else group("All programs", "All PAPs")
    excluded = {"house_controls": 0, "no_house": 0, "senate_unlinked_rows": 0,
                "senate_unlinked_php": 0, "linked_house_amount_mismatches": 0}
    for c in bundle["chains"]:
        h, s = c.get("house"), c.get("senate")
        if not h or h.get("allocation_kind") == "control":
            excluded["house_controls" if h else "no_house"] += 1
            if s:
                excluded["senate_unlinked_rows"] += 1
                excluded["senate_unlinked_php"] += s.get("sv_php") or 0
            continue
        record = project_record(c)
        program, pap = record["program"], record["pap"]
        if grouping == "office":
            region, office, kind = record["region"], record["office"], record["office_type"]
            key = (region, office)
            g = groups.setdefault(key, {**group(*key), "region": region, "office": office, "office_type": kind})
        else:
            key = (program, pap)
            g = groups.setdefault(key, group(*key))
        house, senate = record["house_php"], record["senate_php"]
        if s and s.get("gab_php") != house:
            excluded["linked_house_amount_mismatches"] += 1
        bucket = record["bucket"]
        for row in (g, total):
            add(row["total"], house, senate)
            add(row["documents"][bucket], house, senate)
            if record["flagged"]:
                add(row["flagged"], house, senate)
            for code in set(record["flags"]):
                add(row["flags"][code], house, senate)
            for family in record["families"]:
                add(row["families"][family], house, senate)
    return {"grouping": grouping, "groups": sorted(groups.values(), key=lambda r: (r["program"], r["pap"])),
            "total": total, "excluded": excluded, "flag_catalog": bundle["flag_catalog"],
            "inputs": bundle["inputs"]}

def write_report(report, stem):
    (DATA / (stem + ".json")).write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")
    office_mode = report["grouping"] == "office"
    labels = ["region", "office", "office_type"] if office_mode else ["program", "pap"]
    fields = [*labels, "dimension", "category", *metric()]
    with (DATA / (stem + ".csv")).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in [report["total"], *report["groups"]]:
            categories = [("total", "all", row["total"]), ("flags", "any", row["flagged"])]
            categories += [(dim, k, m) for dim in ("documents", "families", "flags") for k, m in row[dim].items()]
            identity = {"region": row["program"], "office": row["pap"], "office_type": row.get("office_type", "All offices")} if office_mode else {"program": row["program"], "pap": row["pap"]}
            for dim, k, m in categories:
                writer.writerow({**identity, "dimension": dim, "category": k, **m})

def main():
    bundle = json.loads((DATA / "dpwh.json").read_text())
    report = build(bundle)
    offices = build(bundle, "office")
    write_report(report, "dpwh-pap-flags")
    write_report(offices, "dpwh-deo-flags")
    records = [r for c in bundle["chains"] if (r := project_record(c)) is not None]
    (DATA / "dpwh-finding-records.json").write_text(json.dumps({"records": records, "inputs": bundle["inputs"]}, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("FINDING_RECORDS", len(records))
    print("OFFICE_REPORT", json.dumps({"groups": len(offices["groups"]), "total": offices["total"]["total"], "types": {k: sum(r["office_type"] == k for r in offices["groups"]) for k in sorted({r["office_type"] for r in offices["groups"]})}}, ensure_ascii=False))
    # Compact build log for verifying the report without downloading large files.
    print("PAP_REPORT_START")
    print("program|pap|house_count|house_php|senate_count|senate_php|none_n|none_php|partial_n|partial_php|complete_n|complete_php|unchecked_n|unchecked_php|flagged_n|flagged_php (Senate buckets)")
    for row in [report["total"], *report["groups"]]:
        vals = [row["program"], row["pap"], *row["total"].values()]
        for k in BUCKETS:
            vals += [row["documents"][k]["senate_count"], row["documents"][k]["senate_php"]]
        vals += [row["flagged"]["senate_count"], row["flagged"]["senate_php"]]
        print("|".join(map(str, vals)))
    print("EXCLUSIONS", json.dumps(report["excluded"]))
    print("PAP_REPORT_END")

if __name__ == "__main__":
    main()
