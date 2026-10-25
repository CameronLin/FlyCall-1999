#!/usr/bin/env python3
"""Independent structural, quota, privacy-pattern and duplicate validation."""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "data/1999_synthetic"
OUT = DATA / "formal_v1.0.0"
PILOT = DATA / "pilot_v1.2.3.jsonl"
PILOT_PREVIOUS = DATA / "pilot_v1.2.2.jsonl"
TAXONOMY = DATA / "taxonomy_v1.3.yaml"
MERGE_MAP = DATA / "family_merge_map_v1.0.yaml"
MANIFEST = DATA / "formal_split_manifest_frozen_v1.0.yaml"
FINAL_JSONL = OUT / "formal_dataset_v1.0.0.jsonl"
FINAL_CSV = OUT / "formal_dataset_v1.0.0.csv"
FILTERED = OUT / "filtered/formal_filtered_v1.0.0.jsonl"
REPORT = OUT / "validation_report_v1.0.md"

EXPECTED_SOURCE_HASHES = {
    "pilot_v1.2.3.jsonl": "ece9d147088c901aa16d5249b4199638329848d88123824c6796d83df0a75b08",
    "taxonomy_expansion_draft_v1.3.md": "221a39a61dc5de14e423ac3f2985b751ffb30070464660270b3e177c98917f5c",
    "family_merge_map_draft_v1.1.yaml": "933c29507ba1f9aaa5a1ecfaa69a25abd1f1122a21f57be0ccfccbd276172eb0",
    "formal_split_manifest_draft_v1.2.yaml": "7e070248c856cce6756b7b520001e6c6194b4b895d1253e4d1aa5757c2a47e02",
    "taxonomy_v1.2.1.yaml": "a4049235521203d011cae81019ffbf89cde7234a9611dfc26a8d167463581613",
    "FlyCall_1999_助理獨立複核決定_v1.0.xlsx": "04d22ffbfbfd59bd4870916d8c2793ef9c66cbfbcab5cd1e9c0526f00c29e74e",
    "independent_review_decisions_v1.0.md": "77cd24215212f98feb3960a64dee48929ce1e0674290e312df5d73b4b7e0e442",
}
SOURCE_PATHS = {
    "pilot_v1.2.3.jsonl": DATA / "pilot_v1.2.3.jsonl",
    "taxonomy_expansion_draft_v1.3.md": DATA / "taxonomy_expansion_draft_v1.3.md",
    "family_merge_map_draft_v1.1.yaml": DATA / "family_merge_map_draft_v1.1.yaml",
    "formal_split_manifest_draft_v1.2.yaml": DATA / "formal_split_manifest_draft_v1.2.yaml",
    "taxonomy_v1.2.1.yaml": DATA / "taxonomy_v1.2.1.yaml",
    "FlyCall_1999_助理獨立複核決定_v1.0.xlsx": ROOT / "outputs/flycall-1999-review-decisions-v1/FlyCall_1999_助理獨立複核決定_v1.0.xlsx",
    "independent_review_decisions_v1.0.md": ROOT / "outputs/flycall-1999-review-decisions-v1/independent_review_decisions_v1.0.md",
}
REQUIRED_FIELDS = [
    "id", "transcript", "label_id", "label_name", "scenario_id",
    "scenario_family_id", "split", "is_synthetic", "speaker_map",
    "generator_model", "prompt_version", "review_status",
]
SPLITS = ("train", "validation", "test")
CATEGORY_ORDER = ["sidewalk_maintenance", "road_surface_defect", "park_general_maintenance", "waste_truck_service", "street_cleaning"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def yaml_data(path: Path) -> dict:
    ruby = 'require "yaml"; require "json"; print JSON.generate(YAML.safe_load(File.read(ARGV[0]), permitted_classes: [], permitted_symbols: [], aliases: true))'
    return json.loads(subprocess.check_output(["ruby", "-EUTF-8", "-e", ruby, str(path)], text=True))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except Exception as exc:
            raise ValueError(f"{path}:{line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_no}: JSON value is not an object")
        rows.append(row)
    return rows


def cjk_count(text: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]", text))


def normalize(text: str) -> str:
    return re.sub(r"[\s\u3000，。；：！？、,.!?;:'\"（）()【】\[\]{}<>《》…—\-]+", "", text)


def check(condition: bool, issue: str, issues: list[str]) -> None:
    if not condition:
        issues.append(issue)


def validate() -> tuple[list[str], dict]:
    issues: list[str] = []
    summary: dict = {}
    for name, expected in EXPECTED_SOURCE_HASHES.items():
        path = SOURCE_PATHS[name]
        if not path.is_file():
            issues.append(f"來源檔缺少：{name}")
            continue
        actual = sha256(path)
        summary.setdefault("source_hashes", {})[name] = actual
        check(actual == expected, f"來源雜湊與凍結前紀錄不一致：{name}", issues)

    taxonomy = yaml_data(TAXONOMY)
    merge_map = yaml_data(MERGE_MAP)
    manifest = yaml_data(MANIFEST)
    check(taxonomy.get("version") == "1.3", "正式 taxonomy 版本不是 1.3", issues)
    check(taxonomy.get("status") == "approved_for_formal_generation", "正式 taxonomy 狀態錯誤", issues)
    check(merge_map.get("status") == "approved_for_formal_generation", "family merge map 狀態錯誤", issues)
    check(manifest.get("manifest_version") == "frozen-1.0" and manifest.get("status") == "frozen", "manifest 版本或狀態錯誤", issues)
    check("draft_note" not in manifest.get("split_policy", {}), "凍結 manifest 仍有未核准／未凍結草案註記", issues)
    check(manifest.get("formal_dataset_target") == 1000 and manifest.get("records_per_category") == 200, "正式資料目標不是 1,000／每類 200", issues)
    check(manifest.get("pilot", {}).get("included_in_formal_target") is False, "manifest 將 Pilot 納入正式目標", issues)
    check(manifest.get("pilot", {}).get("split") == "pilot", "Pilot split 標記錯誤", issues)

    tax_by_label = {}
    all_tax_families = {}
    revisions = []
    for label in taxonomy.get("labels", []):
        lid = label.get("label_id")
        active = [f for f in label.get("scenario_families", []) if f.get("active") is True]
        ids = [f.get("scenario_family_id") for f in active]
        check(len(ids) == len(set(ids)), f"taxonomy 家族 ID 重複：{lid}", issues)
        tax_by_label[lid] = {f["scenario_family_id"]: f for f in active}
        for fid, family in tax_by_label[lid].items():
            if family.get("source_decision") == "revise":
                revisions.append(fid)
            all_tax_families[fid] = lid
    check(len(all_tax_families) == 66, f"taxonomy 活動家族數不是 66：{len(all_tax_families)}", issues)
    tax_counts = {lid: len(fams) for lid, fams in tax_by_label.items()}
    expected_family_counts = dict(zip(CATEGORY_ORDER, [14, 14, 15, 12, 11]))
    check(tax_counts == expected_family_counts, f"taxonomy 類別家族數不符：{tax_counts}", issues)
    check(len(revisions) == 18, f"taxonomy revise 家族數不是 18：{len(revisions)}", issues)
    merges = merge_map.get("merges", [])
    check(len(merges) == 9 and merge_map.get("merged_family_count") == 9, f"merge 數不是 9：{len(merges)}", issues)
    check(merge_map.get("active_family_count") == 66, "merge map 活動家族數不是 66", issues)
    check(merge_map.get("unresolved_conditional_routes") == [], "merge map 尚有未處理條件路由", issues)
    merge_sources = [m.get("source_family_id") for m in merges]
    check(len(merge_sources) == len(set(merge_sources)), "merge source family ID 重複", issues)
    for merge in merges:
        check(merge.get("source_family_id") not in all_tax_families, f"merge source 仍在活動 taxonomy：{merge.get('source_family_id')}", issues)
        targets = merge.get("target_family_ids", [])
        check(bool(targets), f"merge 沒有目標：{merge.get('source_family_id')}", issues)
        for target in targets:
            check(target in all_tax_families, f"merge 目標無效：{merge.get('source_family_id')} -> {target}", issues)

    cat_rows = manifest.get("categories", [])
    manifest_by_label = {c.get("label_id"): c for c in cat_rows}
    check(set(manifest_by_label) == set(CATEGORY_ORDER), "manifest 類別缺漏或多出", issues)
    family_split: dict[str, str] = {}
    quota_by_family: dict[str, int] = {}
    family_label: dict[str, str] = {}
    per_category_manifest = {}
    for category in cat_rows:
        lid = category.get("label_id")
        families = category.get("families", [])
        ids = [f.get("scenario_family_id") for f in families]
        check(len(ids) == len(set(ids)), f"manifest 家族 ID 重複：{lid}", issues)
        check(set(ids) == set(tax_by_label.get(lid, {})), f"manifest 與 taxonomy 家族不一致：{lid}", issues)
        split_fams = Counter(f.get("split") for f in families)
        split_records = Counter(f.get("split") for f in families for _ in range(int(f.get("planned_records", 0))))
        target_split = {s: int(category.get("split_totals", {}).get(s, -1)) for s in SPLITS}
        check(category.get("target_records") == 200, f"manifest 類別目標不是 200：{lid}", issues)
        check(target_split == {"train": 140, "validation": 30, "test": 30}, f"manifest 類別 split 配額錯誤：{lid} {target_split}", issues)
        check(dict(split_records) == target_split, f"逐家族配額未加總到 split 目標：{lid} {dict(split_records)}", issues)
        declared_family_counts = category.get("family_counts", {})
        check({s: split_fams.get(s, 0) for s in SPLITS} == {s: declared_family_counts.get(s) for s in SPLITS}, f"manifest 家族數欄位與家族清單不符：{lid}", issues)
        per_category_manifest[lid] = {"family_counts": {s: split_fams.get(s, 0) for s in SPLITS}, "record_counts": dict(split_records)}
        for split in SPLITS:
            quotas = [int(f.get("planned_records", 0)) for f in families if f.get("split") == split]
            check(bool(quotas) and min(quotas) > 0, f"manifest 存在零配額家族或空 split：{lid}/{split}", issues)
            check(bool(quotas) and max(quotas) - min(quotas) <= 1, f"同類同 split 家族配額未平均：{lid}/{split}", issues)
        for family in families:
            fid = family.get("scenario_family_id")
            split = family.get("split")
            family_split[fid] = split
            family_label[fid] = lid
            quota_by_family[fid] = int(family.get("planned_records", 0))
    check(len(family_split) == 66, f"manifest 家族數不是 66：{len(family_split)}", issues)
    declared_total = manifest.get("total_split_records", {})
    actual_total = {s: sum(x["record_counts"].get(s, 0) for x in per_category_manifest.values()) for s in SPLITS}
    check(actual_total == {"train": 700, "validation": 150, "test": 150}, f"全體 split 配額錯誤：{actual_total}", issues)
    check(declared_total == actual_total, "manifest 全體筆數摘要與家族配額不符", issues)
    declared_family_total = manifest.get("total_split_families", {})
    actual_family_total = {s: sum(x["family_counts"].get(s, 0) for x in per_category_manifest.values()) for s in SPLITS}
    check(actual_family_total == declared_family_total, "manifest 全體家族摘要與家族清單不符", issues)
    for group in manifest.get("split_policy", {}).get("related_family_groups", []):
        ids = group.get("scenario_family_ids", [])
        actual_splits = {family_split.get(fid) for fid in ids}
        check(all(fid in family_split for fid in ids), f"相關家族群組有無效 ID：{group.get('group_id')}", issues)
        check(actual_splits == {group.get("split")}, f"相關家族跨 split：{group.get('group_id')} -> {actual_splits}", issues)

    pilot_rows = read_jsonl(PILOT)
    old_pilot_rows = read_jsonl(PILOT_PREVIOUS)
    pilot_by_id = {r.get("id"): r for r in pilot_rows}
    old_by_id = {r.get("id"): r for r in old_pilot_rows}
    check(len(pilot_rows) == 50 and len(pilot_by_id) == 50, "Pilot 不是 50 筆唯一 ID", issues)
    check(set(pilot_by_id) == set(old_by_id) and len(old_pilot_rows) == 50, "Pilot v1.2.2/v1.2.3 ID 集合不一致", issues)
    revised_pilot_ids = {"TPE1999-V12-037", "TPE1999-V12-038", "TPE1999-V12-048", "TPE1999-V12-050"}
    transcript_changes = set()
    pilot_nontranscript_changes = []
    for rid in set(pilot_by_id) & set(old_by_id):
        current, old = pilot_by_id[rid], old_by_id[rid]
        if current.get("transcript") != old.get("transcript"):
            transcript_changes.add(rid)
        for key in set(current) | set(old):
            if key != "transcript" and current.get(key) != old.get(key):
                pilot_nontranscript_changes.append(f"{rid}:{key}")
    check(transcript_changes == revised_pilot_ids, f"Pilot 修改逐字稿 ID 不符：{sorted(transcript_changes)}", issues)
    check(not pilot_nontranscript_changes, f"Pilot 非逐字稿欄位變動：{pilot_nontranscript_changes[:5]}", issues)
    check(all(r.get("split") == "pilot" and r.get("review_status") == "pending_manual_review" for r in pilot_rows), "Pilot split/review_status 被更動", issues)
    check(not any(r.get("id") in {p.get("id") for p in pilot_rows} for r in read_jsonl(FINAL_JSONL) if FINAL_JSONL.exists()), "正式資料混入 Pilot ID", issues)

    rows = read_jsonl(FINAL_JSONL)
    check(len(rows) == 1000, f"正式 JSONL 筆數不是 1,000：{len(rows)}", issues)
    ids = [r.get("id") for r in rows]
    scenario_ids = [r.get("scenario_id") for r in rows]
    check(len(ids) == len(set(ids)), "正式資料 ID 重複", issues)
    check(len(scenario_ids) == len(set(scenario_ids)), "正式資料 scenario_id 重複", issues)
    check(not (set(ids) & set(pilot_by_id)), "正式 ID 與 Pilot ID 重疊", issues)
    label_counts = Counter(r.get("label_id") for r in rows)
    label_split = Counter((r.get("label_id"), r.get("split")) for r in rows)
    record_family_split: dict[str, set[str]] = defaultdict(set)
    record_family_count = Counter()
    family_observed = {}
    labels_by_id = {c["label_id"]: c for c in cat_rows}
    cjk_min = 10**9
    line_counts = Counter()
    exact_norms = Counter()
    cjk_values = []
    transcript_errors = []
    for row in rows:
        rid = row.get("id", "<missing-id>")
        if list(row.keys()) != REQUIRED_FIELDS:
            transcript_errors.append(f"{rid}:欄位集合或順序錯誤")
        lid = row.get("label_id")
        fid = row.get("scenario_family_id")
        if lid not in labels_by_id:
            transcript_errors.append(f"{rid}:未知類別 {lid}")
        elif row.get("label_name") != labels_by_id[lid].get("label_name"):
            transcript_errors.append(f"{rid}:label_name 不符")
        if fid not in family_split or family_label.get(fid) != lid:
            transcript_errors.append(f"{rid}:family_id 不屬於該類別 {fid}")
        elif row.get("split") != family_split[fid]:
            transcript_errors.append(f"{rid}:family split 與 manifest 不符")
        record_family_split[fid].add(row.get("split"))
        record_family_count[fid] += 1
        family_observed[fid] = lid
        if row.get("is_synthetic") is not True or row.get("review_status") != "pending_manual_review":
            transcript_errors.append(f"{rid}:合成或複核狀態錯誤")
        if row.get("speaker_map") != {"R": "客服", "L": "來電民眾"}:
            transcript_errors.append(f"{rid}:聲道角色錯誤")
        transcript = row.get("transcript", "")
        lines = transcript.splitlines()
        line_counts[len(lines)] += 1
        chars = cjk_count(transcript)
        cjk_values.append(chars)
        cjk_min = min(cjk_min, chars)
        if len(lines) not in {9, 11, 13}:
            transcript_errors.append(f"{rid}:發言行數 {len(lines)}")
        if not lines or lines[0][:2] != "R:" or lines[-1][:2] != "R:":
            transcript_errors.append(f"{rid}:開場／收尾角色錯誤")
        if any(line[:2] != ("R:" if idx % 2 == 0 else "L:") for idx, line in enumerate(lines)):
            transcript_errors.append(f"{rid}:R/L 次序錯誤")
        if chars < 200:
            transcript_errors.append(f"{rid}:中文字數 {chars}")
        if any(name and name in transcript for name in {c.get("label_name", "") for c in cat_rows}):
            transcript_errors.append(f"{rid}:逐字稿透露分類名稱")
        if re.search(r"(?:09\d{8}|0[2-8]\d?[- ]?\d{6,8}|[A-Z][12]\d{8}|\d{1,4}\s*(?:號|巷|弄|樓|室))", transcript, re.I):
            transcript_errors.append(f"{rid}:疑似電話、身分證或門牌格式")
        if re.search(r"我叫|姓名|手機號碼|行動電話|聯絡電話|電話號碼|身分證|門牌|地址是|住址", transcript):
            transcript_errors.append(f"{rid}:個資提示詞")
        if re.search(r"會派人|保證|保證處理|已安排|已經處理|明天會|馬上處理|一定會", transcript):
            transcript_errors.append(f"{rid}:客服處理承諾")
        exact_norms[normalize(transcript)] += 1
    check(label_counts == {lid: 200 for lid in CATEGORY_ORDER}, f"類別筆數錯誤：{dict(label_counts)}", issues)
    cat_codes = {"sidewalk_maintenance": "SW", "road_surface_defect": "RD", "park_general_maintenance": "PK", "waste_truck_service": "WT", "street_cleaning": "SC"}
    id_errors = []
    for lid, code in cat_codes.items():
        seqs = []
        for row in rows:
            if row.get("label_id") != lid:
                continue
            match = re.fullmatch(rf"TPE1999-FORMAL-{code}-(\d{{4}})", row.get("id", ""))
            if not match:
                id_errors.append(f"{row.get('id')}:ID 格式／類別碼錯誤")
                continue
            seq = int(match.group(1))
            seqs.append(seq)
            if row.get("scenario_id") != f"SCENARIO-FORMAL-{code}-{seq:04d}":
                id_errors.append(f"{row.get('id')}:scenario_id 與正式 ID 不相符")
        if sorted(seqs) != list(range(1, 201)):
            id_errors.append(f"{lid}:ID 序號不是 0001–0200")
    check(not id_errors, f"正式 ID 規則錯誤：{id_errors[:8]}", issues)
    expected_per_label_split = {(lid, split): amount for lid in CATEGORY_ORDER for split, amount in zip(SPLITS, [140, 30, 30])}
    observed_per_label_split = {key: label_split.get(key, 0) for key in expected_per_label_split}
    check(observed_per_label_split == expected_per_label_split, f"類別／split 配額錯誤：{observed_per_label_split}", issues)
    check(set(family_observed) == set(family_split), "正式資料家族集合與凍結 manifest 不一致", issues)
    check(all(len(splits) == 1 for splits in record_family_split.values()), "正式資料同一 scenario_family_id 跨 split", issues)
    check(record_family_count == quota_by_family, "正式資料逐家族筆數與 frozen quota 不一致", issues)
    for group in manifest.get("split_policy", {}).get("related_family_groups", []):
        group_splits = {s for fid in group.get("scenario_family_ids", []) for s in record_family_split.get(fid, set())}
        check(group_splits == {group.get("split")}, f"正式資料相關家族跨 split：{group.get('group_id')}", issues)
    check(not transcript_errors, f"逐字稿／欄位錯誤 {len(transcript_errors)} 筆：{transcript_errors[:8]}", issues)
    check(sum(n - 1 for n in exact_norms.values() if n > 1) == 0, "正式資料含完全重複逐字稿", issues)

    # Character trigram Jaccard scan across every final transcript.
    normalized = [normalize(row.get("transcript", "")) for row in rows]
    trigrams = [{text[i:i+3] for i in range(max(0, len(text) - 2))} for text in normalized]
    max_similarity = (0.0, None, None)
    high_similarity = []
    for i, left in enumerate(trigrams):
        for j in range(i + 1, len(trigrams)):
            right = trigrams[j]
            union = left | right
            similarity = len(left & right) / len(union) if union else 1.0
            if similarity > max_similarity[0]:
                max_similarity = (similarity, rows[i].get("id"), rows[j].get("id"))
            if similarity >= 0.72:
                high_similarity.append((similarity, rows[i].get("id"), rows[j].get("id")))
    check(not high_similarity, f"3-gram Jaccard >= 0.72 的近似重複 {len(high_similarity)} 對", issues)

    check(FILTERED.is_file() and FILTERED.read_bytes() == FINAL_JSONL.read_bytes(), "篩選資料與最終 JSONL 不一致", issues)
    csv_rows = list(csv.DictReader(FINAL_CSV.open(encoding="utf-8", newline="")))
    check(len(csv_rows) == len(rows), f"最終 CSV 筆數錯誤：{len(csv_rows)}", issues)
    csv_errors = []
    for idx, (csv_row, json_row) in enumerate(zip(csv_rows, rows), start=1):
        try:
            speaker_map = ast.literal_eval(csv_row["speaker_map"])
        except Exception:
            speaker_map = None
        parsed_synthetic = csv_row["is_synthetic"].strip().lower() == "true"
        if any(csv_row.get(k) != str(json_row.get(k)) for k in ["id", "transcript", "label_id", "label_name", "scenario_id", "scenario_family_id", "split", "generator_model", "prompt_version", "review_status"]):
            csv_errors.append(f"row {idx}:field mismatch")
        if speaker_map != json_row.get("speaker_map") or parsed_synthetic != json_row.get("is_synthetic"):
            csv_errors.append(f"row {idx}:typed field mismatch")
    check(not csv_errors, f"CSV／JSONL 對照錯誤 {len(csv_errors)} 筆：{csv_errors[:5]}", issues)

    generation_manifest = list(csv.DictReader((OUT / "generation_manifest.csv").open(encoding="utf-8", newline="")))
    check(len(generation_manifest) == 1000, "generation_manifest.csv 不是 1,000 列", issues)
    plan_ids = {r.get("id") for r in generation_manifest}
    check(plan_ids == set(ids), "generation manifest ID 與最終資料不一致", issues)
    plan_by_id = {r.get("id"): r for r in generation_manifest}
    row_by_id = {r.get("id"): r for r in rows}
    plan_errors = []
    for rid in set(plan_by_id) & set(row_by_id):
        for key in ("scenario_id", "label_id", "label_name", "scenario_family_id", "split"):
            if plan_by_id[rid].get(key) != str(row_by_id[rid].get(key)):
                plan_errors.append(f"{rid}:{key}")
    check(not plan_errors, f"generation manifest 對應資料列錯誤：{plan_errors[:8]}", issues)
    batch_manifest = list(csv.DictReader((OUT / "batch_manifest.csv").open(encoding="utf-8", newline="")))
    check(len(batch_manifest) == 20 and {r.get("batch") for r in batch_manifest} == {f"{i:03d}" for i in range(1, 21)}, "batch manifest 不是 20 批", issues)
    batch_errors = []
    accepted_batch_records = {}
    for batch_no in range(1, 21):
        path = OUT / "filtered_batches" / f"batch_{batch_no:03d}.jsonl"
        batch_rows = read_jsonl(path)
        if len(batch_rows) != 50:
            batch_errors.append(f"{batch_no:03d}:{len(batch_rows)} records")
        if any(r.get("id") not in set(ids) for r in batch_rows):
            batch_errors.append(f"{batch_no:03d}:unknown id")
        if len({r.get("id") for r in batch_rows}) != 50:
            batch_errors.append(f"{batch_no:03d}:duplicate batch ID")
        for batch_row in batch_rows:
            rid = batch_row.get("id")
            if rid in accepted_batch_records:
                batch_errors.append(f"{batch_no:03d}:ID repeated across batches {rid}")
            accepted_batch_records[rid] = batch_row
            if rid in row_by_id and batch_row != row_by_id[rid]:
                batch_errors.append(f"{batch_no:03d}:row differs from final {rid}")
        matching = next((r for r in batch_manifest if r.get("batch") == f"{batch_no:03d}"), {})
        if matching.get("filtered_sha256") != sha256(path):
            batch_errors.append(f"{batch_no:03d}:hash mismatch")
        if int(matching.get("records", -1)) != 50:
            batch_errors.append(f"{batch_no:03d}:batch manifest count mismatch")
        if matching:
            batch_labels = {str(k): int(v) for k, v in json.loads(matching.get("label_counts", "{}")).items()}
            batch_splits = {str(k): int(v) for k, v in json.loads(matching.get("split_counts", "{}")).items()}
            if batch_labels != dict(Counter(r.get("label_id") for r in batch_rows)):
                batch_errors.append(f"{batch_no:03d}:batch label summary mismatch")
            if batch_splits != dict(Counter(r.get("split") for r in batch_rows)):
                batch_errors.append(f"{batch_no:03d}:batch split summary mismatch")
    check(not batch_errors, f"批次錯誤：{batch_errors[:8]}", issues)
    batch_ids = [r.get("id") for n in range(1, 21) for r in read_jsonl(OUT / "filtered_batches" / f"batch_{n:03d}.jsonl")]
    check(len(batch_ids) == 1000 and len(set(batch_ids)) == 1000 and set(batch_ids) == set(ids), "批次資料與最終資料不是同一組 1,000 筆", issues)
    check(accepted_batch_records == row_by_id, "批次資料的內容與最終資料不完全相同", issues)
    log_rows = read_jsonl(OUT / "batch_log.jsonl")
    latest_accepted = {n: [r for r in log_rows if r.get("batch") == n and r.get("status") == "accepted"][-1] for n in range(1, 21) if any(r.get("batch") == n and r.get("status") == "accepted" for r in log_rows)}
    log_errors = []
    if set(latest_accepted) != set(range(1, 21)):
        log_errors.append("latest accepted rows missing")
    for n, row in latest_accepted.items():
        if row.get("filtered_sha256") != sha256(OUT / "filtered_batches" / f"batch_{n:03d}.jsonl"):
            log_errors.append(f"batch {n:03d} latest log hash mismatch")
    check(not log_errors, f"batch log 錯誤：{log_errors}", issues)
    checkpoint = json.loads((OUT / "checkpoint.json").read_text(encoding="utf-8"))
    check(checkpoint.get("status") == "complete" and len(checkpoint.get("completed_batches", [])) == 20 and checkpoint.get("final_records") == 1000, "批次檢查點未完整", issues)
    check(checkpoint.get("final_jsonl_sha256") == sha256(FINAL_JSONL) and checkpoint.get("final_csv_sha256") == sha256(FINAL_CSV), "checkpoint 與最終檔案 hash 不符", issues)

    raw_files = sorted((OUT / "raw_generated").glob("batch_*_attempt_*.jsonl"))
    raw_all = OUT / "raw_generated/formal_raw_all_attempts_v1.0.0.jsonl"
    raw_count = len(read_jsonl(raw_all)) if raw_all.exists() else 0
    check(raw_all.is_file() and raw_count == sum(len(read_jsonl(p)) for p in raw_files), "原始生成彙整檔與批次原始候選數不一致", issues)
    check((OUT / "superseded/first_generator_pass/SUPERSEDED.md").is_file(), "未保留第一輪修整前生成產物說明", issues)

    summary.update({
        "taxonomy_family_counts": tax_counts,
        "revised_family_count": len(revisions),
        "merge_count": len(merges),
        "manifest_family_totals": actual_family_total,
        "manifest_record_totals": actual_total,
        "per_category_manifest": per_category_manifest,
        "records": len(rows),
        "label_counts": dict(label_counts),
        "label_split_counts": {f"{lid}/{split}": observed_per_label_split[(lid, split)] for lid in CATEGORY_ORDER for split in SPLITS},
        "families_observed": len(record_family_count),
        "cjk_minimum": cjk_min,
        "cjk_mean": round(sum(cjk_values) / len(cjk_values), 2) if cjk_values else 0,
        "transcript_lines": dict(line_counts),
        "exact_duplicate_excess": sum(n - 1 for n in exact_norms.values() if n > 1),
        "near_duplicate_metric": "character 3-gram Jaccard",
        "near_duplicate_threshold": 0.72,
        "near_duplicate_pairs": len(high_similarity),
        "max_near_duplicate": {"similarity": round(max_similarity[0], 4), "id_a": max_similarity[1], "id_b": max_similarity[2]},
        "pilot_records": len(pilot_rows),
        "pilot_changed_transcripts": sorted(transcript_changes),
        "pilot_nontranscript_changes": pilot_nontranscript_changes,
        "raw_attempt_files": len(raw_files),
        "raw_candidate_records": raw_count,
        "filtered_records": len(read_jsonl(FILTERED)) if FILTERED.exists() else 0,
        "batch_count": len(batch_manifest),
        "batch_size": 50,
        "final_jsonl_sha256": sha256(FINAL_JSONL),
        "final_csv_sha256": sha256(FINAL_CSV),
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
    })
    return issues, summary


def render_report(summary: dict) -> str:
    cat_names = {
        "sidewalk_maintenance": "人行道維護",
        "road_surface_defect": "道路凹陷、不平、有高低差",
        "park_general_maintenance": "公園綠地及設施維護",
        "waste_truck_service": "垃圾車清運及服務事項",
        "street_cleaning": "路面清潔",
    }
    lines = [
        "# 正式合成通話資料驗證報告 v1.0",
        "",
        f"驗證時間（UTC）：{datetime.now(timezone.utc).isoformat()}",
        f"結果：**{summary['status']}**",
        "",
        "## 數量與配額",
        "",
        "| 類別 | 家族 train/validation/test | 筆數 train/validation/test | 總筆數 |",
        "|---|---:|---:|---:|",
    ]
    for lid in CATEGORY_ORDER:
        item = summary["per_category_manifest"][lid]
        fam = item["family_counts"]
        rec = item["record_counts"]
        lines.append(f"| {cat_names[lid]} | {fam['train']}/{fam['validation']}/{fam['test']} | {rec['train']}/{rec['validation']}/{rec['test']} | 200 |")
    lines.extend([
        f"| **全體** | **{summary['manifest_family_totals']['train']}/{summary['manifest_family_totals']['validation']}/{summary['manifest_family_totals']['test']}** | **{summary['manifest_record_totals']['train']}/{summary['manifest_record_totals']['validation']}/{summary['manifest_record_totals']['test']}** | **{summary['records']}** |",
        "",
        "- 有效情境家族：66 個；taxonomy revise：18 個；merge：9 個，未解條件路由為 0。",
        "- 逐家族配額皆為正整數；同類、同 split 內配額最多相差 1 筆。",
        "- 五類正式筆數各 200，總計 1,000；Pilot 50 筆維持 `split=pilot`，不計入正式資料。",
        "- 垃圾車家族配置採 7/2/3（train/validation/test），因需將七個 stop-presence／到達順序相關家族置於同一 split；仍精確維持每類 140/30/30。",
        "",
        "## 結構、個資與重複度",
        "",
        f"- 最終 JSONL/CSV：{summary['records']} 筆；filtered JSONL：{summary['filtered_records']} 筆；兩者一致。",
        f"- 發言行數分布：{summary['transcript_lines']}；中文字數最低 {summary['cjk_minimum']}，平均 {summary['cjk_mean']}。",
        "- 欄位、ID 唯一性、角色（R=客服、L=來電民眾）、`is_synthetic=true`、`pending_manual_review`、label/family/split 對應、逐家族 quota 與 R/L 順序均通過程式檢查。",
        "- 沒有偵測到電話、身分證、門牌格式、個資提示詞、分類名稱洩漏或客服處理承諾。這是格式／規則檢查，不等同人工逐筆內容核准。",
        f"- 完全重複：{summary['exact_duplicate_excess']} 筆；字元 3-gram Jaccard ≥ {summary['near_duplicate_threshold']} 的近似重複：{summary['near_duplicate_pairs']} 對；最高相似度 {summary['max_near_duplicate']['similarity']}（{summary['max_near_duplicate']['id_a']} / {summary['max_near_duplicate']['id_b']}）。",
        "- 相關家族群組及特別指定的道路縱向轉換／隆起／波狀起伏、垃圾車假日／週末均依 frozen manifest 同 split。",
        "",
        "## Pilot 與來源保護",
        "",
        "- Pilot v1.2.3 共 50 筆；對照 v1.2.2，僅指定 V12-037、038、048、050 的逐字稿改變，其他欄位未變；全部仍為 `pending_manual_review`。",
        "- 凍結前輸入來源均與記錄的 SHA-256 相符；原始 Pilot、taxonomy v1.2.1、草案 manifest、merge map 與複核決定檔未被覆寫。",
        "- 所有新資料仍是 `pending_manual_review`，並未冒充人工簽核；Pilot 狀態也未改成通過。",
        "",
        "## 批次與重現性",
        "",
        f"- {summary['batch_count']} 批，每批 {summary['batch_size']} 筆；批次清單、原始候選、篩選批次、checkpoint 及 append-only batch log 均保留。原始候選共 {summary['raw_candidate_records']} 筆、{summary['raw_attempt_files']} 個批次嘗試檔。",
        "- 第一輪生成產物因抽樣發現話術模板化而保留於 `superseded/first_generator_pass/`；最終輸出只使用後續通過檢查的 20 個批次。",
        "- 逐字稿由場景家族變化庫與確定性模板組裝生成；自動驗證不取代人工自然度與單一主訴語義複核。",
        "",
        "## 最終檔案 SHA-256",
        "",
        f"- `formal_dataset_v1.0.0.jsonl`: `{summary['final_jsonl_sha256']}`",
        f"- `formal_dataset_v1.0.0.csv`: `{summary['final_csv_sha256']}`",
        "",
        "## 未解決項目",
        "",
    ])
    if summary["issues"]:
        lines.extend(f"- {issue}" for issue in summary["issues"])
    else:
        lines.append("- 未發現結構或配額阻塞。仍待後續逐筆人工複核自然度、單一主要案件問題及情境合理性；全體資料尚未人工通過。")
    return "\n".join(lines) + "\n"


def main() -> int:
    issues, summary = validate()
    REPORT.write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report={REPORT}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
