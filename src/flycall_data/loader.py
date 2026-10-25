"""Read-only loader and contract checks for a frozen formal dataset."""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "id",
    "transcript",
    "label_id",
    "label_name",
    "scenario_id",
    "scenario_family_id",
    "split",
    "is_synthetic",
    "speaker_map",
    "generator_model",
    "prompt_version",
    "review_status",
)
SPLITS = ("train", "validation", "test")
SOURCE_NAMES = ("jsonl", "csv", "taxonomy", "manifest")
EXPECTED_RECORD_COUNT = 1000
EXPECTED_CATEGORY_COUNT = 5
EXPECTED_RECORDS_PER_CATEGORY = 200
EXPECTED_TOTAL_SPLITS = {"train": 700, "validation": 150, "test": 150}
EXPECTED_CATEGORY_SPLITS = {"train": 140, "validation": 30, "test": 30}


@dataclass(frozen=True)
class DatasetPaths:
    """Explicit locations of the four files that form the frozen contract."""

    jsonl_path: Path
    csv_path: Path
    taxonomy_path: Path
    frozen_manifest_path: Path


@dataclass(frozen=True)
class ContractIssue:
    """One machine-readable difference between inputs and the frozen contract."""

    code: str
    message: str
    source: str | None = None
    record_id: str | None = None
    expected: Any = None
    actual: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "source": self.source,
            "record_id": self.record_id,
            "expected": self.expected,
            "actual": self.actual,
        }


class DatasetContractError(ValueError):
    """Raised when any dataset source disagrees with the frozen contract."""

    def __init__(self, issues: list[ContractIssue] | tuple[ContractIssue, ...]):
        self.issues = tuple(issues)
        detail = "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues)
        super().__init__(f"Frozen dataset contract failed ({len(self.issues)} issue(s)): {detail}")


@dataclass(frozen=True)
class DatasetBundle:
    """Validated records and summary metadata for downstream analysis."""

    records: tuple[dict[str, Any], ...]
    label_names: dict[str, str]
    split_counts: dict[str, int]
    label_split_counts: dict[str, dict[str, int]]
    family_splits: dict[str, str]
    audit_summary: dict[str, Any]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _issue(
    issues: list[ContractIssue],
    code: str,
    message: str,
    *,
    source: str | None = None,
    record_id: str | None = None,
    expected: Any = None,
    actual: Any = None,
) -> None:
    issues.append(ContractIssue(code, message, source, record_id, expected, actual))


def _read_source(path: Path, source: str, issues: list[ContractIssue]) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError as exc:
        _issue(issues, "source_unreadable", f"無法讀取 {path}: {exc}", source=source)
        return None


def _parse_jsonl(raw: bytes, issues: list[ContractIssue]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _issue(issues, "jsonl_encoding", f"JSONL 不是有效 UTF-8：{exc}", source="jsonl")
        return rows
    for line_number, line in enumerate(content.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            _issue(
                issues,
                "jsonl_parse_error",
                f"第 {line_number} 行 JSON 無法解析：{exc.msg}",
                source="jsonl",
                actual={"line": line_number, "column": exc.colno},
            )
            continue
        if not isinstance(row, dict):
            _issue(
                issues,
                "jsonl_row_type",
                f"第 {line_number} 行必須是 JSON object。",
                source="jsonl",
                actual=type(row).__name__,
            )
            continue
        rows.append(row)
    return rows


def _parse_csv(raw: bytes, issues: list[ContractIssue]) -> list[dict[str, Any]]:
    try:
        content = raw.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content, newline=""))
        if reader.fieldnames is None:
            _issue(issues, "csv_header_missing", "CSV 缺少標題列。", source="csv")
            return []
        if tuple(reader.fieldnames) != REQUIRED_FIELDS:
            _issue(
                issues,
                "csv_schema_mismatch",
                "CSV 欄位與正式 schema 不一致。",
                source="csv",
                expected=list(REQUIRED_FIELDS),
                actual=reader.fieldnames,
            )
        rows: list[dict[str, Any]] = []
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                _issue(
                    issues,
                    "csv_row_width",
                    f"CSV 第 {row_number} 列欄位數與標題不一致。",
                    source="csv",
                    actual=row,
                )
                continue
            normalized: dict[str, Any] = dict(row)
            bool_value = str(row.get("is_synthetic", "")).strip().lower()
            if bool_value in {"true", "false"}:
                normalized["is_synthetic"] = bool_value == "true"
            try:
                normalized["speaker_map"] = ast.literal_eval(row.get("speaker_map", ""))
            except (ValueError, SyntaxError):
                _issue(
                    issues,
                    "csv_speaker_map_invalid",
                    f"CSV 第 {row_number} 列 speaker_map 無法解析。",
                    source="csv",
                    record_id=row.get("id"),
                    actual=row.get("speaker_map"),
                )
            rows.append(normalized)
        return rows
    except UnicodeDecodeError as exc:
        _issue(issues, "csv_encoding", f"CSV 不是有效 UTF-8：{exc}", source="csv")
        return []
    except csv.Error as exc:
        _issue(issues, "csv_parse_error", f"CSV 無法解析：{exc}", source="csv")
        return []


def _parse_yaml(raw: bytes, source: str, issues: list[ContractIssue]) -> dict[str, Any] | None:
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _issue(issues, "yaml_encoding", f"YAML 不是有效 UTF-8：{exc}", source=source)
        return None
    ruby = (
        'require "yaml"; require "json"; '
        'print JSON.generate(YAML.safe_load(STDIN.read, '
        'permitted_classes: [], permitted_symbols: [], aliases: true))'
    )
    try:
        result = subprocess.run(
            ["ruby", "-EUTF-8", "-e", ruby],
            input=raw,
            capture_output=True,
            check=True,
        )
        value = json.loads(result.stdout.decode("utf-8"))
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        stderr = getattr(exc, "stderr", b"")
        detail = stderr.decode("utf-8", errors="replace").strip() if isinstance(stderr, bytes) else str(exc)
        _issue(issues, "yaml_parse_error", f"{source} 無法解析：{detail or exc}", source=source)
        return None
    if not isinstance(value, dict):
        _issue(
            issues,
            "yaml_root_type",
            f"{source} 根節點必須是 mapping。",
            source=source,
            actual=type(value).__name__,
        )
        return None
    return value


def _validate_record_schema(rows: list[dict[str, Any]], issues: list[ContractIssue]) -> None:
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        record_id = row.get("id") if isinstance(row.get("id"), str) else None
        missing = [field for field in REQUIRED_FIELDS if field not in row]
        extras = sorted(set(row) - set(REQUIRED_FIELDS))
        if missing:
            _issue(
                issues,
                "record_missing_fields",
                f"資料列 {index} 缺少必要欄位：{', '.join(missing)}。",
                source="jsonl",
                record_id=record_id,
                expected=list(REQUIRED_FIELDS),
                actual=sorted(row),
            )
        if extras:
            _issue(
                issues,
                "record_unexpected_fields",
                f"資料列 {index} 含非契約欄位：{', '.join(extras)}。",
                source="jsonl",
                record_id=record_id,
                actual=extras,
            )
        for field in REQUIRED_FIELDS:
            if field not in row:
                continue
            value = row[field]
            if field == "is_synthetic":
                if not isinstance(value, bool):
                    _issue(
                        issues,
                        "record_field_type",
                        f"{field} 必須是 boolean。",
                        source="jsonl",
                        record_id=record_id,
                        expected="boolean",
                        actual=type(value).__name__,
                    )
            elif field == "speaker_map":
                if not isinstance(value, dict):
                    _issue(
                        issues,
                        "record_field_type",
                        "speaker_map 必須是 object。",
                        source="jsonl",
                        record_id=record_id,
                        expected="object",
                        actual=type(value).__name__,
                    )
            elif not isinstance(value, str):
                _issue(
                    issues,
                    "record_field_type",
                    f"{field} 必須是字串。",
                    source="jsonl",
                    record_id=record_id,
                    expected="string",
                    actual=type(value).__name__,
                )
            elif not value.strip():
                _issue(
                    issues,
                    "record_field_empty",
                    f"{field} 不可為空。",
                    source="jsonl",
                    record_id=record_id,
                    expected="non-empty",
                    actual=value,
                )
        if record_id:
            if record_id in seen_ids:
                _issue(
                    issues,
                    "duplicate_record_id",
                    f"record ID 重複：{record_id}。",
                    source="jsonl",
                    record_id=record_id,
                )
            seen_ids.add(record_id)


def _taxonomy_indexes(taxonomy: dict[str, Any], issues: list[ContractIssue]) -> tuple[dict[str, str], dict[str, str]]:
    labels: dict[str, str] = {}
    family_labels: dict[str, str] = {}
    taxonomy_labels = taxonomy.get("labels")
    if not isinstance(taxonomy_labels, list):
        _issue(issues, "taxonomy_labels_missing", "taxonomy 缺少 labels 清單。", source="taxonomy")
        return labels, family_labels
    for label in taxonomy_labels:
        if not isinstance(label, dict):
            _issue(issues, "taxonomy_label_invalid", "taxonomy labels 含非 mapping 項目。", source="taxonomy")
            continue
        label_id = label.get("label_id")
        label_name = label.get("label_name")
        if not isinstance(label_id, str) or not isinstance(label_name, str):
            _issue(issues, "taxonomy_label_invalid", "taxonomy label 缺少 label_id 或 label_name。", source="taxonomy", actual=label)
            continue
        if label_id in labels:
            _issue(issues, "duplicate_taxonomy_label", f"taxonomy label_id 重複：{label_id}。", source="taxonomy")
        labels[label_id] = label_name
        families = label.get("scenario_families", [])
        if not isinstance(families, list):
            _issue(issues, "taxonomy_families_invalid", f"{label_id} 的 scenario_families 必須是清單。", source="taxonomy")
            continue
        for family in families:
            if not isinstance(family, dict):
                _issue(issues, "taxonomy_family_invalid", f"{label_id} 含非 mapping 家族項目。", source="taxonomy")
                continue
            family_id = family.get("scenario_family_id")
            if not isinstance(family_id, str) or not family_id:
                _issue(issues, "taxonomy_family_invalid", f"{label_id} 的家族缺少 scenario_family_id。", source="taxonomy", actual=family)
                continue
            if not isinstance(family.get("active"), bool):
                _issue(issues, "taxonomy_family_active_invalid", f"{family_id} 缺少 boolean active 狀態。", source="taxonomy", actual=family.get("active"))
                continue
            if family.get("active") is not True:
                continue
            if family_id in family_labels:
                _issue(issues, "duplicate_taxonomy_family", f"有效 scenario_family_id 重複：{family_id}。", source="taxonomy", actual=[family_labels[family_id], label_id])
            family_labels[family_id] = label_id
    return labels, family_labels


def _manifest_indexes(
    manifest: dict[str, Any], issues: list[ContractIssue]
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[str, str, int]]]:
    categories = manifest.get("categories")
    category_by_id: dict[str, dict[str, Any]] = {}
    family_specs: dict[str, tuple[str, str, int]] = {}
    if not isinstance(categories, list):
        _issue(issues, "manifest_categories_missing", "manifest 缺少 categories 清單。", source="manifest")
        return category_by_id, family_specs
    for category in categories:
        if not isinstance(category, dict):
            _issue(issues, "manifest_category_invalid", "manifest categories 含非 mapping 項目。", source="manifest")
            continue
        label_id = category.get("label_id")
        if not isinstance(label_id, str):
            _issue(issues, "manifest_category_invalid", "manifest category 缺少 label_id。", source="manifest", actual=category)
            continue
        if label_id in category_by_id:
            _issue(issues, "duplicate_manifest_category", f"manifest label_id 重複：{label_id}。", source="manifest")
        category_by_id[label_id] = category
        families = category.get("families")
        if not isinstance(families, list):
            _issue(issues, "manifest_families_invalid", f"{label_id} 的 families 必須是清單。", source="manifest")
            continue
        for family in families:
            if not isinstance(family, dict):
                _issue(issues, "manifest_family_invalid", f"{label_id} 含非 mapping 家族項目。", source="manifest")
                continue
            family_id = family.get("scenario_family_id")
            split = family.get("split")
            quota = family.get("planned_records")
            if not isinstance(family_id, str) or split not in SPLITS or not isinstance(quota, int) or isinstance(quota, bool):
                _issue(issues, "manifest_family_invalid", f"{label_id} 的家族缺少有效 ID、split 或 planned_records。", source="manifest", actual=family)
                continue
            if family_id in family_specs:
                _issue(issues, "duplicate_manifest_family", f"manifest scenario_family_id 重複：{family_id}。", source="manifest")
            family_specs[family_id] = (label_id, split, quota)
    return category_by_id, family_specs


def load_frozen_dataset(paths: DatasetPaths) -> DatasetBundle:
    """Load records only after all four sources pass the frozen data contract."""

    issues: list[ContractIssue] = []
    path_map = {
        "jsonl": Path(paths.jsonl_path),
        "csv": Path(paths.csv_path),
        "taxonomy": Path(paths.taxonomy_path),
        "manifest": Path(paths.frozen_manifest_path),
    }
    source_bytes = {name: _read_source(path, name, issues) for name, path in path_map.items()}
    if issues:
        raise DatasetContractError(issues)
    raw = {name: value for name, value in source_bytes.items() if value is not None}
    source_hashes = {name: _sha256(raw[name]) for name in SOURCE_NAMES}

    records = _parse_jsonl(raw["jsonl"], issues)
    csv_records = _parse_csv(raw["csv"], issues)
    taxonomy = _parse_yaml(raw["taxonomy"], "taxonomy", issues)
    manifest = _parse_yaml(raw["manifest"], "manifest", issues)
    _validate_record_schema(records, issues)

    if len(records) != len(csv_records):
        _issue(
            issues,
            "jsonl_csv_row_count_mismatch",
            "JSONL 與 CSV 資料列數不一致。",
            source="csv",
            expected=len(records),
            actual=len(csv_records),
        )
    for index, (json_row, csv_row) in enumerate(zip(records, csv_records), start=1):
        for field in REQUIRED_FIELDS:
            if json_row.get(field) != csv_row.get(field):
                _issue(
                    issues,
                    "jsonl_csv_content_mismatch",
                    f"JSONL 與 CSV 第 {index} 筆的 {field} 不一致。",
                    source="csv",
                    record_id=json_row.get("id"),
                    expected=json_row.get(field),
                    actual=csv_row.get(field),
                )
                break

    if issues:
        raise DatasetContractError(issues)

    if taxonomy is None or manifest is None:
        raise DatasetContractError(issues)
    if taxonomy.get("status") != "approved_for_formal_generation":
        _issue(issues, "taxonomy_status_mismatch", "taxonomy 不是核准的正式版本。", source="taxonomy", expected="approved_for_formal_generation", actual=taxonomy.get("status"))
    if not taxonomy.get("version"):
        _issue(issues, "taxonomy_version_missing", "taxonomy 缺少版本欄位。", source="taxonomy")
    if manifest.get("status") != "frozen" or not str(manifest.get("manifest_version", "")).startswith("frozen-"):
        _issue(issues, "manifest_not_frozen", "split manifest 必須是 frozen 版本。", source="manifest", expected="status=frozen", actual={"status": manifest.get("status"), "version": manifest.get("manifest_version")})
    if manifest.get("formal_dataset_target") != EXPECTED_RECORD_COUNT or manifest.get("records_per_category") != EXPECTED_RECORDS_PER_CATEGORY:
        _issue(issues, "manifest_target_mismatch", "manifest 正式資料目標必須為 1,000 筆、每類 200 筆。", source="manifest", expected={"total": 1000, "per_category": 200}, actual={"total": manifest.get("formal_dataset_target"), "per_category": manifest.get("records_per_category")})

    taxonomy_labels, taxonomy_families = _taxonomy_indexes(taxonomy, issues)
    manifest_categories, manifest_families = _manifest_indexes(manifest, issues)
    if len(taxonomy_labels) != EXPECTED_CATEGORY_COUNT or len(manifest_categories) != EXPECTED_CATEGORY_COUNT:
        _issue(
            issues,
            "category_count_mismatch",
            "正式資料必須包含五個主類別。",
            source="manifest",
            expected=EXPECTED_CATEGORY_COUNT,
            actual={"taxonomy": len(taxonomy_labels), "manifest": len(manifest_categories)},
        )
    speaker_section = taxonomy.get("speaker_map")
    speaker_channels = speaker_section.get("channels") if isinstance(speaker_section, dict) else None
    if not isinstance(speaker_channels, dict) or not speaker_channels:
        _issue(issues, "taxonomy_speaker_map_missing", "taxonomy 缺少有效 speaker_map.channels。", source="taxonomy")
    else:
        for row in records:
            if row.get("speaker_map") != speaker_channels:
                _issue(
                    issues,
                    "record_speaker_map_mismatch",
                    "資料列 speaker_map 與 taxonomy 固定聲道設定不一致。",
                    source="jsonl",
                    record_id=row.get("id"),
                    expected=speaker_channels,
                    actual=row.get("speaker_map"),
                )
    taxonomy_schema = taxonomy.get("schema")
    if not isinstance(taxonomy_schema, dict):
        _issue(issues, "taxonomy_schema_invalid", "taxonomy schema 必須是 mapping。", source="taxonomy", actual=taxonomy_schema)
        taxonomy_schema = {}
    expected_review_status = taxonomy_schema.get("formal_review_status")
    for row in records:
        label_id = row.get("label_id")
        expected_name = taxonomy_labels.get(label_id)
        if expected_name is not None and row.get("label_name") != expected_name:
            _issue(
                issues,
                "record_label_name_mismatch",
                f"資料列 label_name 與 taxonomy 中 {label_id} 的名稱不一致。",
                source="jsonl",
                record_id=row.get("id"),
                expected=expected_name,
                actual=row.get("label_name"),
            )
    if set(taxonomy_labels) != set(manifest_categories):
        _issue(issues, "taxonomy_manifest_labels_mismatch", "taxonomy 與 manifest 的 label_id 集合不一致。", source="manifest", expected=sorted(taxonomy_labels), actual=sorted(manifest_categories))
    for label_id in set(taxonomy_labels) & set(manifest_categories):
        manifest_name = manifest_categories[label_id].get("label_name")
        if manifest_name != taxonomy_labels[label_id]:
            _issue(issues, "taxonomy_manifest_label_name_mismatch", f"{label_id} 的標籤名稱不一致。", source="manifest", expected=taxonomy_labels[label_id], actual=manifest_name)
    if set(taxonomy_families) != set(manifest_families):
        _issue(issues, "taxonomy_manifest_families_mismatch", "taxonomy 有效家族與 manifest 家族集合不一致。", source="manifest", expected=sorted(taxonomy_families), actual=sorted(manifest_families))
    for family_id in set(taxonomy_families) & set(manifest_families):
        if taxonomy_families[family_id] != manifest_families[family_id][0]:
            _issue(issues, "taxonomy_manifest_family_label_mismatch", f"{family_id} 在 taxonomy 與 manifest 的類別不一致。", source="manifest", expected=taxonomy_families[family_id], actual=manifest_families[family_id][0])
        if manifest_families[family_id][2] <= 0:
            _issue(issues, "manifest_family_quota_invalid", f"{family_id} 的配額必須大於 0。", source="manifest", expected="> 0", actual=manifest_families[family_id][2])

    target = manifest.get("formal_dataset_target", EXPECTED_RECORD_COUNT)
    per_category = manifest.get("records_per_category", EXPECTED_RECORDS_PER_CATEGORY)
    if len(records) != EXPECTED_RECORD_COUNT or len(records) != target:
        _issue(issues, "record_count_mismatch", "正式資料總筆數與 manifest 不一致。", source="jsonl", expected=target, actual=len(records))
    label_counts = Counter(row.get("label_id") for row in records)
    expected_label_ids = set(manifest_categories)
    for label_id in sorted(expected_label_ids):
        count = label_counts.get(label_id, 0)
        if count != per_category:
            _issue(issues, "label_quota_mismatch", f"{label_id} 筆數與每類配額不一致。", source="jsonl", expected=per_category, actual=count)
    unexpected_labels = sorted(set(label_counts) - expected_label_ids)
    if unexpected_labels:
        _issue(issues, "unknown_record_labels", "資料含 manifest 未定義的標籤。", source="jsonl", expected=sorted(expected_label_ids), actual=unexpected_labels)

    split_counts = Counter(row.get("split") for row in records)
    expected_total_splits = manifest.get("total_split_records")
    if not isinstance(expected_total_splits, dict):
        _issue(issues, "manifest_total_split_records_invalid", "manifest total_split_records 必須是 mapping。", source="manifest", actual=expected_total_splits)
        expected_total_splits = {}
    for split in SPLITS:
        expected_count = expected_total_splits.get(split)
        if expected_count != EXPECTED_TOTAL_SPLITS[split]:
            _issue(
                issues,
                "manifest_split_quota_mismatch",
                f"manifest 全體 {split} 配額不符合正式資料契約。",
                source="manifest",
                expected=EXPECTED_TOTAL_SPLITS[split],
                actual=expected_count,
            )
        if split_counts.get(split, 0) != expected_count:
            _issue(issues, "total_split_quota_mismatch", f"全體 {split} 筆數與 manifest 不一致。", source="jsonl", expected=expected_count, actual=split_counts.get(split, 0))

    label_split_counts: dict[str, dict[str, int]] = {}
    for label_id, category in manifest_categories.items():
        observed = Counter(row.get("split") for row in records if row.get("label_id") == label_id)
        label_split_counts[label_id] = {split: observed.get(split, 0) for split in SPLITS}
        expected_splits = category.get("split_totals")
        if not isinstance(expected_splits, dict):
            _issue(issues, "manifest_category_split_totals_invalid", f"{label_id} 的 split_totals 必須是 mapping。", source="manifest", actual=expected_splits)
            expected_splits = {}
        for split in SPLITS:
            expected_count = expected_splits.get(split)
            if expected_count != EXPECTED_CATEGORY_SPLITS[split]:
                _issue(
                    issues,
                    "manifest_category_split_quota_mismatch",
                    f"{label_id} 的 {split} 配額不符合正式資料契約。",
                    source="manifest",
                    expected=EXPECTED_CATEGORY_SPLITS[split],
                    actual=expected_count,
                )
            if observed.get(split, 0) != expected_count:
                _issue(issues, "label_split_quota_mismatch", f"{label_id} 的 {split} 筆數與 manifest 不一致。", source="jsonl", expected=expected_count, actual=observed.get(split, 0))
        if category.get("target_records") != per_category:
            _issue(issues, "manifest_category_target_mismatch", f"{label_id} 的 target_records 不等於每類配額。", source="manifest", expected=per_category, actual=category.get("target_records"))
        family_specs_for_category = {
            family_id: spec for family_id, spec in manifest_families.items() if spec[0] == label_id
        }
        for split in SPLITS:
            planned_count = sum(quota for _, planned_split, quota in family_specs_for_category.values() if planned_split == split)
            if planned_count != expected_splits.get(split):
                _issue(
                    issues,
                    "manifest_family_quota_split_mismatch",
                    f"{label_id} 的 {split} 家族配額加總與 split_totals 不一致。",
                    source="manifest",
                    expected=expected_splits.get(split),
                    actual=planned_count,
                )
        declared_family_counts = category.get("family_counts")
        if not isinstance(declared_family_counts, dict):
            _issue(issues, "manifest_category_family_counts_invalid", f"{label_id} 的 family_counts 必須是 mapping。", source="manifest", actual=declared_family_counts)
            declared_family_counts = {}
        for split in SPLITS:
            planned_family_count = sum(1 for _, planned_split, _ in family_specs_for_category.values() if planned_split == split)
            if declared_family_counts.get(split) != planned_family_count:
                _issue(
                    issues,
                    "manifest_family_count_mismatch",
                    f"{label_id} 的 {split} 家族數與 manifest family_counts 不一致。",
                    source="manifest",
                    expected=planned_family_count,
                    actual=declared_family_counts.get(split),
                )

    split_policy = manifest.get("split_policy")
    if not isinstance(split_policy, dict):
        _issue(issues, "manifest_split_policy_invalid", "manifest split_policy 必須是 mapping。", source="manifest", actual=split_policy)
        split_policy = {}
    related_groups = split_policy.get("related_family_groups", [])
    if not isinstance(related_groups, list):
        _issue(issues, "manifest_related_groups_invalid", "related_family_groups 必須是清單。", source="manifest")
    else:
        for group in related_groups:
            if not isinstance(group, dict):
                _issue(issues, "manifest_related_group_invalid", "related_family_groups 含非 mapping 項目。", source="manifest")
                continue
            group_id = group.get("group_id", "(未命名)")
            group_split = group.get("split")
            group_label_id = group.get("label_id")
            group_families = group.get("scenario_family_ids", [])
            if group_split not in SPLITS or not isinstance(group_families, list):
                _issue(issues, "manifest_related_group_invalid", f"{group_id} 缺少有效 split 或 scenario_family_ids。", source="manifest", actual=group)
                continue
            for family_id in group_families:
                if not isinstance(family_id, str):
                    _issue(issues, "manifest_related_family_invalid", f"{group_id} 含無效 scenario_family_id。", source="manifest", actual=family_id)
                    continue
                spec = manifest_families.get(family_id)
                if spec is None:
                    _issue(issues, "manifest_related_family_unknown", f"{group_id} 引用了 manifest 未定義的家族：{family_id}。", source="manifest", actual=family_id)
                elif spec[1] != group_split:
                    _issue(
                        issues,
                        "manifest_related_group_split_mismatch",
                        f"{group_id} 的相關家族沒有全部安排在同一 split。",
                        source="manifest",
                        expected=group_split,
                        actual={"family_id": family_id, "split": spec[1]},
                    )
                elif isinstance(group_label_id, str) and spec[0] != group_label_id:
                    _issue(
                        issues,
                        "manifest_related_group_label_mismatch",
                        f"{group_id} 中的家族類別與群組 label_id 不一致。",
                        source="manifest",
                        expected=group_label_id,
                        actual={"family_id": family_id, "label_id": spec[0]},
                    )

    declared_total_split_records = expected_total_splits
    declared_total_split_families = manifest.get("total_split_families", {})
    if not isinstance(declared_total_split_families, dict):
        _issue(issues, "manifest_total_split_families_invalid", "manifest total_split_families 必須是 mapping。", source="manifest", actual=declared_total_split_families)
        declared_total_split_families = {}
    for split in SPLITS:
        category_record_total = 0
        for category in manifest_categories.values():
            category_splits = category.get("split_totals")
            if isinstance(category_splits, dict):
                quota = category_splits.get(split, 0)
                if isinstance(quota, int) and not isinstance(quota, bool):
                    category_record_total += quota
        category_family_total = sum(
            1
            for _, planned_split, _ in manifest_families.values()
            if planned_split == split
        )
        if declared_total_split_records.get(split) != category_record_total:
            _issue(
                issues,
                "manifest_total_split_records_mismatch",
                f"manifest 全體 {split} 筆數與類別配額加總不一致。",
                source="manifest",
                expected=category_record_total,
                actual=declared_total_split_records.get(split),
            )
        if declared_total_split_families.get(split) != category_family_total:
            _issue(
                issues,
                "manifest_total_split_families_mismatch",
                f"manifest 全體 {split} 家族數與類別家族配置不一致。",
                source="manifest",
                expected=category_family_total,
                actual=declared_total_split_families.get(split),
            )

    record_family_counts = Counter(row.get("scenario_family_id") for row in records)
    family_observed_splits: dict[str, set[str]] = defaultdict(set)
    for row in records:
        family_id = row.get("scenario_family_id")
        label_id = row.get("label_id")
        split = row.get("split")
        family_observed_splits[family_id].add(split)
        if row.get("is_synthetic") is not True:
            _issue(issues, "record_not_synthetic", "正式資料列 is_synthetic 必須為 true。", source="jsonl", record_id=row.get("id"), expected=True, actual=row.get("is_synthetic"))
        if expected_review_status is not None and row.get("review_status") != expected_review_status:
            _issue(issues, "record_review_status_mismatch", "資料列 review_status 與 taxonomy 正式設定不一致。", source="jsonl", record_id=row.get("id"), expected=expected_review_status, actual=row.get("review_status"))
        if family_id not in taxonomy_families:
            _issue(issues, "unknown_record_family", f"資料使用 taxonomy 未定義的家族：{family_id}。", source="jsonl", record_id=row.get("id"), actual=family_id)
        elif taxonomy_families[family_id] != label_id:
            _issue(issues, "record_family_label_mismatch", f"資料列的家族不屬於其標籤：{family_id}。", source="jsonl", record_id=row.get("id"), expected=taxonomy_families[family_id], actual=label_id)
        spec = manifest_families.get(family_id)
        if spec is None:
            _issue(issues, "unknown_manifest_family", f"資料家族未列於 manifest：{family_id}。", source="jsonl", record_id=row.get("id"), actual=family_id)
        else:
            expected_label, expected_split, _expected_quota = spec
            if label_id != expected_label:
                _issue(issues, "record_manifest_family_label_mismatch", f"{family_id} 的資料標籤與 manifest 不一致。", source="jsonl", record_id=row.get("id"), expected=expected_label, actual=label_id)
            if split != expected_split:
                _issue(issues, "record_manifest_split_mismatch", f"{family_id} 的資料 split 與 manifest 不一致。", source="jsonl", record_id=row.get("id"), expected=expected_split, actual=split)
    for family_id, splits_seen in family_observed_splits.items():
        if len(splits_seen) > 1:
            _issue(issues, "family_cross_split", f"scenario_family_id 跨越多個 split：{family_id}。", source="jsonl", expected="single split", actual=sorted(splits_seen))
    for family_id, (label_id, split, quota) in manifest_families.items():
        observed_count = record_family_counts.get(family_id, 0)
        if observed_count != quota:
            _issue(issues, "family_quota_mismatch", f"{family_id} 筆數與逐家族配額不一致。", source="jsonl", expected=quota, actual=observed_count)
        observed_splits = family_observed_splits.get(family_id, set())
        if observed_count and observed_splits != {split}:
            _issue(issues, "manifest_family_split_mismatch", f"{family_id} 的資料 split 與 manifest 不一致。", source="jsonl", expected=[split], actual=sorted(observed_splits))

    # A load must not alter inputs; compare current bytes to the snapshots parsed above.
    for name, path in path_map.items():
        try:
            after = path.read_bytes()
        except OSError as exc:
            _issue(issues, "source_unreadable_after_load", f"載入後無法再次讀取 {path}: {exc}", source=name)
            continue
        if _sha256(after) != source_hashes[name]:
            _issue(issues, "source_changed_during_load", f"載入期間來源檔內容發生變化：{path}。", source=name, expected=source_hashes[name], actual=_sha256(after))

    if issues:
        raise DatasetContractError(issues)

    family_splits = {family_id: spec[1] for family_id, spec in manifest_families.items()}
    audit_summary = {
        "record_count": len(records),
        "label_count": len(taxonomy_labels),
        "family_count": len(taxonomy_families),
        "split_counts": {split: split_counts.get(split, 0) for split in SPLITS},
        "label_counts": dict(sorted(label_counts.items())),
        "label_split_counts": label_split_counts,
        "source_sha256": source_hashes,
        "manifest_version": manifest.get("manifest_version"),
        "taxonomy_version": taxonomy.get("version"),
    }
    return DatasetBundle(
        records=tuple(records),
        label_names=taxonomy_labels,
        split_counts={split: split_counts.get(split, 0) for split in SPLITS},
        label_split_counts=label_split_counts,
        family_splits=family_splits,
        audit_summary=audit_summary,
    )
