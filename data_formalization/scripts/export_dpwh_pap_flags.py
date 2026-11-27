"""Build PAP-level risk tables from the published DPWH chain snapshot.

House project leaves only. Senate amounts use the linked amendment or the
House amount if Annex A-4 contains no linked amendment. Unlinked Senate
rows and control nodes are excluded and disclosed separately.
"""
import csv
import json
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

def build(bundle):
    groups = {}
    total = group("All programs", "All PAPs")
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
        program = h.get("program") or "Unclassified program"
        pap = h.get("pap") or "No separate PAP heading"
        key = (program, pap)
        g = groups.setdefault(key, group(*key))
        house = h["amount_php"]
        senate = (s.get("sv_php") or 0) if s else house
        if s and s.get("gab_php") != house:
            excluded["linked_house_amount_mismatches"] += 1
        review = c.get("review") or {}
        n = review.get("key_documents_found")
        bucket = "none" if n == 0 else "partial" if n in (1, 2, 3, 4) else "complete" if n == 5 else "unchecked"
        flags = {(f[0], f[1]) for f in c.get("flags", [])}
        families = {family for _, family in flags}
        for row in (g, total):
            add(row["total"], house, senate)
            add(row["documents"][bucket], house, senate)
            if flags or (review.get("red_flags") or 0) > 0:
                add(row["flagged"], house, senate)
            for code, family in flags:
                add(row["flags"][code], house, senate)
            for family in families:
                add(row["families"][family], house, senate)
    return {"groups": sorted(groups.values(), key=lambda r: (r["program"], r["pap"])),
            "total": total, "excluded": excluded, "flag_catalog": bundle["flag_catalog"],
            "inputs": bundle["inputs"]}

def main():
    report = build(json.loads((DATA / "dpwh.json").read_text()))
    (DATA / "dpwh-pap-flags.json").write_text(json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n")
    fields = ["program", "pap", "dimension", "category", *metric()]
    with (DATA / "dpwh-pap-flags.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in [report["total"], *report["groups"]]:
            categories = [("total", "all", row["total"]), ("flags", "any", row["flagged"])]
            categories += [(dim, k, m) for dim in ("documents", "families", "flags") for k, m in row[dim].items()]
            for dim, k, m in categories:
                writer.writerow({"program": row["program"], "pap": row["pap"], "dimension": dim, "category": k, **m})
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
