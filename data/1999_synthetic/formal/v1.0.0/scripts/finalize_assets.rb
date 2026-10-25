#!/usr/bin/env ruby
# Build the approved v1.3 taxonomy, formal merge map, frozen split manifest,
# and generation plan from the verified project drafts. Refuses to overwrite.
require "yaml"
require "json"
require "digest"
require "fileutils"
require "set"

ROOT = File.expand_path("../../../../..", __dir__)
DATA = File.join(ROOT, "data/1999_synthetic")
OUT = File.join(DATA, "formal_v1.0.0")
NOW = "2026-10-12"

sources = {
  "pilot_v1.2.3.jsonl" => File.join(DATA, "pilot_v1.2.3.jsonl"),
  "taxonomy_expansion_draft_v1.3.md" => File.join(DATA, "taxonomy_expansion_draft_v1.3.md"),
  "family_merge_map_draft_v1.1.yaml" => File.join(DATA, "family_merge_map_draft_v1.1.yaml"),
  "formal_split_manifest_draft_v1.2.yaml" => File.join(DATA, "formal_split_manifest_draft_v1.2.yaml"),
  "taxonomy_v1.2.1.yaml" => File.join(DATA, "taxonomy_v1.2.1.yaml"),
  "independent_review_decisions_v1.0.md" => File.join(ROOT, "outputs/flycall-1999-review-decisions-v1/independent_review_decisions_v1.0.md"),
  "FlyCall_1999_助理獨立複核決定_v1.0.xlsx" => File.join(ROOT, "outputs/flycall-1999-review-decisions-v1/FlyCall_1999_助理獨立複核決定_v1.0.xlsx")
}
missing = sources.values.reject { |p| File.file?(p) }
abort("Missing source files: #{missing.join(', ')}") unless missing.empty?

outputs = [
  File.join(DATA, "taxonomy_v1.3.yaml"),
  File.join(DATA, "family_merge_map_v1.0.yaml"),
  File.join(DATA, "formal_split_manifest_frozen_v1.0.yaml"),
  File.join(DATA, "formal_generation_plan_v1.3.md"),
  File.join(OUT, "preflight_and_freeze_record_v1.0.md")
]
existing = outputs.select { |p| File.exist?(p) }
abort("Refusing to overwrite existing outputs: #{existing.join(', ')}") unless existing.empty?

taxonomy_base = YAML.safe_load(File.read(sources.fetch("taxonomy_v1.2.1.yaml")), permitted_classes: [], permitted_symbols: [], aliases: true)
merge_map = YAML.safe_load(File.read(sources.fetch("family_merge_map_draft_v1.1.yaml")), permitted_classes: [], permitted_symbols: [], aliases: true)
manifest = YAML.safe_load(File.read(sources.fetch("formal_split_manifest_draft_v1.2.yaml")), permitted_classes: [], permitted_symbols: [], aliases: true)
pilot_rows = File.readlines(sources.fetch("pilot_v1.2.3.jsonl"), chomp: true).reject(&:empty?).map { |line| JSON.parse(line) }
abort("Pilot must have 50 rows") unless pilot_rows.length == 50
abort("Pilot must remain pending_manual_review") unless pilot_rows.all? { |r| r["review_status"] == "pending_manual_review" }
abort("Pilot must be separate from formal data") unless pilot_rows.all? { |r| r["split"] == "pilot" }

heading_to_label = {
  "人行道維護" => "sidewalk_maintenance",
  "道路凹陷、不平、有高低差" => "road_surface_defect",
  "一般公園綠地管理及設施維護" => "park_general_maintenance",
  "垃圾車清運及服務事項" => "waste_truck_service",
  "路面清潔" => "street_cleaning"
}
family_rows = []
current_label = nil
File.foreach(sources.fetch("taxonomy_expansion_draft_v1.3.md"), encoding: "UTF-8") do |line|
  if line.start_with?("## ") && line.include?("個有效家族")
    heading = line.sub(/^##\s+/, "").split("（").first
    current_label = heading_to_label[heading]
    abort("Unrecognized taxonomy heading: #{heading}") unless current_label
  elsif line.start_with?("| `FAM-")
    cells = line.sub(/^\|/, "").sub(/\|\s*$/, "").split("|").map(&:strip)
    next unless cells.length == 5
    id = cells[0].match(/`(FAM-[A-Z0-9-]+)`/)&.[](1)
    next unless id
    status_text, core, variation, boundary = cells[1..4]
    decision = status_text.include?("修訂草案") ? "revise" : "pass"
    family_rows << {
      "label_id" => current_label,
      "scenario_family_id" => id,
      "source_status" => status_text,
      "decision" => decision,
      "case_core" => core,
      "variation_axes" => variation,
      "inclusion_and_exclusion_boundary" => boundary
    }
  end
end
abort("Expected 66 active family rows; found #{family_rows.length}") unless family_rows.length == 66
ids = family_rows.map { |f| f.fetch("scenario_family_id") }
abort("Duplicate active family IDs") unless ids.uniq.length == ids.length

decisions_text = File.read(sources.fetch("independent_review_decisions_v1.0.md"), encoding: "UTF-8")
expected_revise_ids = decisions_text[/## 情境家族 revise.*?(?=## 情境家族 merge)/m].to_s.scan(/`(FAM-[A-Z0-9-]+)`：/).flatten.to_set
expected_merge_ids = decisions_text[/## 情境家族 merge.*?(?=## Pass 家族)/m].to_s.scan(/`(FAM-[A-Z0-9-]+)` →/).flatten.to_set
actual_revise_ids = family_rows.select { |f| f["decision"] == "revise" }.map { |f| f["scenario_family_id"] }.to_set
abort("Taxonomy revise IDs do not match the adopted decisions") unless expected_revise_ids == actual_revise_ids && actual_revise_ids.length == 18
abort("Expected 9 source merge rules") unless merge_map.fetch("merges").length == 9 && expected_merge_ids.length == 9
active_ids = ids.to_set
merge_sources = merge_map.fetch("merges").map { |m| m.fetch("source_family_id") }.to_set
abort("A merged source is still active") unless (active_ids & merge_sources).empty?
invalid_targets = merge_map.fetch("merges").flat_map { |m| m.fetch("target_family_ids") }.uniq - active_ids.to_a
abort("Invalid merge targets: #{invalid_targets.join(', ')}") unless invalid_targets.empty?

pilot_source = "pilot_v1.2.3.jsonl"
pilot_label_names = pilot_rows.group_by { |r| r.fetch("label_id") }.transform_values { |rs| rs.map { |r| r.fetch("label_name") }.uniq }
abort("Pilot label_name is inconsistent within a category") unless pilot_label_names.values.all? { |a| a.length == 1 }

taxonomy = taxonomy_base.dup
taxonomy["version"] = "1.3"
taxonomy["status"] = "approved_for_formal_generation"
taxonomy["pilot_source"] = {
  "current_file" => pilot_source,
  "records" => 50,
  "split" => "pilot",
  "included_in_formal_target" => false,
  "review_status" => "pending_manual_review",
  "revised_transcripts" => %w[TPE1999-V12-037 TPE1999-V12-038 TPE1999-V12-048 TPE1999-V12-050],
  "remaining_records_unchanged_from_v1.2.2" => 46
}
taxonomy["speaker_map"] = {
  "status" => "fixed_for_synthetic_generation",
  "note" => "本合成文字資料固定沿用專案聲道設定；不代表對其他資料格式作推定。",
  "channels" => { "R" => "客服", "L" => "來電民眾" }
}
taxonomy["revision_notes"] = Array(taxonomy["revision_notes"]) + [
  "v1.3 依使用者於 2026-10-12 採納的助理獨立複核決定 v1.0 建立正式 taxonomy；保留全部舊版草案。",
  "套用 18 個情境家族界線修訂、9 個 merge；活動家族共 66 個，五類為 14／14／15／12／11。",
  "正式資料另新增 1,000 筆，Pilot 50 筆獨立，不納入正式配額。"
]
taxonomy["sources"] = sources.transform_values { |p| { "path" => p.delete_prefix(ROOT + "/"), "sha256" => Digest::SHA256.file(p).hexdigest } }
taxonomy["formal_generation"] = {
  "target_records" => 1000,
  "records_per_category" => 200,
  "split_ratio" => { "train" => 0.70, "validation" => 0.15, "test" => 0.15 },
  "split_manifest" => "formal_split_manifest_frozen_v1.0.yaml",
  "generated_records_review_status" => "pending_manual_review",
  "pilot_included" => false
}
taxonomy["schema"]["formal_minimum_cjk_characters"] = 200
taxonomy["schema"]["formal_turn_count"] = "每筆 8–14 行 R/L 發言；生成器採 9、11、13 行並以 R: 收尾。"
taxonomy["schema"]["formal_records_per_category"] = 200
taxonomy["schema"]["formal_total_records"] = 1000
taxonomy["schema"]["formal_review_status"] = "pending_manual_review"
taxonomy["schema"]["pilot_split"] = "pilot"
taxonomy["schema"]["pilot_current_file"] = pilot_source
pilot_allocations = pilot_rows.group_by { |r| r.fetch("label_id") }.transform_values do |rows|
  rows.group_by { |r| r.fetch("scenario_family_id") }.transform_values(&:length)
end
taxonomy["schema"]["pilot_family_allocation"] = pilot_allocations
taxonomy["schema"]["pilot_family_count_by_category"] = pilot_allocations.transform_values(&:length)
taxonomy["labels"].each do |label|
  rows = family_rows.select { |f| f["label_id"] == label.fetch("label_id") }
  abort("No families for label #{label.fetch('label_id')}") if rows.empty?
  # Use the taxonomy's canonical label name. The v1.2 draft's shortened park label is not authoritative.
  expected = pilot_label_names[label.fetch("label_id")]
  label["label_name"] = expected.first if expected && expected.length == 1
  label["scenario_families"] = rows.map do |f|
    existing = f.fetch("source_status").start_with?("既有")
    {
      "scenario_family_id" => f.fetch("scenario_family_id"),
      "name" => f.fetch("case_core").sub(/[。.]\z/, ""),
      "case_core" => f.fetch("case_core"),
      "variation_axes" => f.fetch("variation_axes"),
      "inclusion_and_exclusion_boundary" => f.fetch("inclusion_and_exclusion_boundary"),
      "source_status" => f.fetch("source_status"),
      "source_decision" => f.fetch("decision"),
      "taxonomy_status" => existing ? "approved_existing" : (f.fetch("decision") == "revise" ? "approved_revised_candidate" : "approved_candidate"),
      "active" => true
    }
  end
end
counts = taxonomy["labels"].map { |l| [l.fetch("label_id"), l.fetch("scenario_families").length] }.to_h
expected_counts = { "sidewalk_maintenance" => 14, "road_surface_defect" => 14, "park_general_maintenance" => 15, "waste_truck_service" => 12, "street_cleaning" => 11 }
abort("Taxonomy category family counts mismatch: #{counts}") unless counts == expected_counts

merge_map = Marshal.load(Marshal.dump(merge_map))
merge_map["map_version"] = "1.0"
merge_map["status"] = "approved_for_formal_generation"
merge_map["source_taxonomy"] = "taxonomy_v1.3.yaml"
merge_map["source_taxonomy_draft"] = "taxonomy_expansion_draft_v1.3.md"
merge_map["decision_authorization"] = "使用者於 2026-10-12 明確採納助理獨立複核決定並授權正式生成。"
merge_map["unresolved_conditional_routes"] = []
merge_map.fetch("merges").each do |m|
  case m.fetch("source_family_id")
  when "FAM-CLEAN-WIND-DISPERSED-LITTER"
    m["target_rule"] = "一般散落物／來源不明 → FAM-CLEAN-SURFACE-DEBRIS；確認因果皮箱滿溢外漏 → FAM-CLEAN-BIN-OVERFLOW；確認因箱體破損外漏 → FAM-CLEAN-BIN-DAMAGE。"
    m["routing_rule"] = "只能根據可觀察的散落物與果皮箱狀態分流；僅有風或來電者猜測，不足以推定箱體為來源。"
  when "FAM-WASTE-RECYCLABLE-STREAM-SERVICE"
    m["target_rule"] = "唯一主要訴求是到達時段 → FAM-WASTE-ARRIVAL-TIME；未見車輛停靠 → FAM-WASTE-MISSED-STOP；等候位置改變或不明 → FAM-WASTE-STOP-LOCATION。"
    m["routing_rule"] = "必須只選一個主要服務問題；排除回收物分類、袋別或政策諮詢。若主要訴求同時不止一項，該筆不生成。"
  when "FAM-WASTE-SCHEDULED-DAY-OMISSION"
    m["target_rule"] = "單一固定停靠點／住戶未服務 → FAM-WASTE-MISSED-STOP；連續街廓／整段路線未服務 → FAM-WASTE-ROUTE-SEGMENT-OMISSION。"
    m["routing_rule"] = "以來電者觀察的未服務範圍判定；不得僅憑單戶推估整段未服務。"
  when "FAM-CLEAN-DOG-WASTE-PERSISTENT-RESIDUE"
    m["target_rule"] = "新出現或不同位置的狗便清理 → FAM-CLEAN-DOG-WASTE；同一舊痕已清掃但仍留存 → FAM-CLEAN-POST-SWEEP-RESIDUE。"
    m["routing_rule"] = "只有明確確認是同一處既有污痕且經過清掃仍殘留時，才分流至 POST-SWEEP；未確認時歸 DOG-WASTE，不推測清掃歷史。"
  end
end

manifest["manifest_version"] = "frozen-1.0"
manifest["status"] = "frozen"
manifest["frozen_at"] = NOW
manifest["freeze_reason"] = "已核對來源版本、家族決定、合併目標、逐家族整數配額及分組隔離；家族配額不為零。"
manifest["formal_dataset_target"] = 1000
manifest["records_per_category"] = 200
manifest["recommended_split"] = "70/15/15"
manifest["sources"]["taxonomy_final"] = "taxonomy_v1.3.yaml"
manifest["sources"]["merge_map_final"] = "family_merge_map_v1.0.yaml"
manifest["sources"]["manifest_source"] = "formal_split_manifest_draft_v1.2.yaml"
manifest["sources"]["taxonomy_expansion_current_draft"] = "taxonomy_expansion_draft_v1.3.md"
manifest["pilot"]["current_draft_file"] = pilot_source
manifest["pilot"]["records"] = 50
manifest["pilot"]["included_in_formal_target"] = false
manifest["pilot"]["review_status"] = "pending_manual_review"
manifest["pilot"]["generation_gate"] = "Pilot 保持獨立且狀態 pending_manual_review；使用者本次已明確採納複核建議並授權正式生成，不變更 Pilot 狀態。"
manifest["split_policy"]["unit"] = "scenario_family_id"
manifest["split_policy"]["isolation"] = "每個有效 scenario_family_id 完整位於唯一 split；列於 related_family_groups 的易混淆家族亦必須共同分組。"
manifest["split_policy"]["family_counts_per_category_by_order"] = ["7/3/4", "7/3/4", "8/3/4", "7/2/3", "4/3/4"]
manifest["split_policy"]["rationale"] = "保留每類 train/validation/test 140/30/30。垃圾車 stop-presence 相關群組與所有條件式合併目標同置 train，避免原 v1.2 的 train/validation 跨 split；因此該類家族配置改為 7/2/3，validation 兩個家族、test 三個家族。"
manifest["split_policy"]["batch_size"] = 50
manifest["split_policy"]["batch_count"] = 20
manifest["split_policy"]["family_quota_rule"] = "每個類別、每個 split 的整數配額採平均分配；餘數依 manifest 家族順序逐一加 1；不得為 0。"
manifest["split_policy"].delete("draft_note")
manifest["split_policy"]["related_family_groups"] = [
  { "group_id" => "road_profile_transition_heave_undulation", "label_id" => "road_surface_defect", "scenario_family_ids" => %w[FAM-ROAD-LONGITUDINAL-TRANSITION FAM-ROAD-PAVEMENT-HEAVE FAM-ROAD-WIDESPREAD-UNDULATION], "split" => "test" },
  { "group_id" => "waste_stop_presence", "label_id" => "waste_truck_service", "scenario_family_ids" => %w[FAM-WASTE-MISSED-STOP FAM-WASTE-ROUTE-SEGMENT-OMISSION FAM-WASTE-PARTIAL-COLLECTION FAM-WASTE-SHORT-DWELL], "split" => "train" },
  { "group_id" => "waste_holiday_weekend_schedule", "label_id" => "waste_truck_service", "scenario_family_ids" => %w[FAM-WASTE-HOLIDAY-SCHEDULE FAM-WASTE-WEEKEND-SCHEDULE], "split" => "test" },
  { "group_id" => "sidewalk_utility_settlement", "label_id" => "sidewalk_maintenance", "scenario_family_ids" => %w[FAM-SW-UTILITY-RESTORATION FAM-SW-LEVEL-SETTLEMENT], "split" => "train" },
  { "group_id" => "sidewalk_ramp_surface_geometry", "label_id" => "sidewalk_maintenance", "scenario_family_ids" => %w[FAM-SW-RAMP-SURFACE FAM-SW-CURB-RAMP-LANDING FAM-SW-FLAT-SURFACE-SLIPPERY], "split" => "test" },
  { "group_id" => "waste_scheduled_day_merge_targets", "label_id" => "waste_truck_service", "scenario_family_ids" => %w[FAM-WASTE-MISSED-STOP FAM-WASTE-ROUTE-SEGMENT-OMISSION], "split" => "train" },
  { "group_id" => "waste_recyclable_service_merge_targets", "label_id" => "waste_truck_service", "scenario_family_ids" => %w[FAM-WASTE-ARRIVAL-TIME FAM-WASTE-MISSED-STOP FAM-WASTE-STOP-LOCATION], "split" => "train" },
  { "group_id" => "waste_arrival_order_boundary", "label_id" => "waste_truck_service", "scenario_family_ids" => %w[FAM-WASTE-ARRIVAL-TIME FAM-WASTE-ROUTE-ORDER-CHANGE], "split" => "train" },
  { "group_id" => "waste_access", "label_id" => "waste_truck_service", "scenario_family_ids" => %w[FAM-WASTE-ALLEY-ACCESS FAM-WASTE-ACCESS-INTERRUPTION], "split" => "validation" },
  { "group_id" => "cleaning_wind_merge_targets", "label_id" => "street_cleaning", "scenario_family_ids" => %w[FAM-CLEAN-SURFACE-DEBRIS FAM-CLEAN-BIN-OVERFLOW FAM-CLEAN-BIN-DAMAGE], "split" => "train" },
  { "group_id" => "cleaning_dog_residue_merge_targets", "label_id" => "street_cleaning", "scenario_family_ids" => %w[FAM-CLEAN-DOG-WASTE FAM-CLEAN-POST-SWEEP-RESIDUE], "split" => "validation" },
  { "group_id" => "cleaning_repeat_and_residue", "label_id" => "street_cleaning", "scenario_family_ids" => %w[FAM-CLEAN-DOG-WASTE FAM-CLEAN-REACCUMULATING-DEBRIS FAM-CLEAN-POST-SWEEP-RESIDUE], "split" => "validation" }
]

assignments = {
  "waste_truck_service" => {
    "train" => %w[FAM-WASTE-MISSED-STOP FAM-WASTE-ARRIVAL-TIME FAM-WASTE-STOP-LOCATION FAM-WASTE-ROUTE-SEGMENT-OMISSION FAM-WASTE-PARTIAL-COLLECTION FAM-WASTE-SHORT-DWELL FAM-WASTE-ROUTE-ORDER-CHANGE],
    "validation" => %w[FAM-WASTE-ALLEY-ACCESS FAM-WASTE-ACCESS-INTERRUPTION],
    "test" => %w[FAM-WASTE-WEEKEND-SCHEDULE FAM-WASTE-HOLIDAY-SCHEDULE FAM-WASTE-COLLECTION-CUE-FAILURE]
  }
}
manifest["categories"].each do |category|
  label = taxonomy.fetch("labels").find { |l| l.fetch("label_id") == category.fetch("label_id") }
  abort("Manifest category not in taxonomy: #{category['label_id']}") unless label
  category["label_name"] = label.fetch("label_name")
  category["target_records"] = 200
  category["split_totals"] = { "train" => 140, "validation" => 30, "test" => 30 }
  family_ids = category.fetch("families").map { |f| f.fetch("scenario_family_id") }
  abort("Manifest family set differs from active taxonomy for #{category['label_id']}") unless family_ids.sort == label.fetch("scenario_families").map { |f| f.fetch("scenario_family_id") }.sort
  if assignments.key?(category.fetch("label_id"))
    split_of = assignments.fetch(category.fetch("label_id")).flat_map { |sp, xs| xs.map { |id| [id, sp] } }.to_h
  else
    split_of = category.fetch("families").to_h { |f| [f.fetch("scenario_family_id"), f.fetch("split")] }
  end
  category.fetch("families").each { |f| f["split"] = split_of.fetch(f.fetch("scenario_family_id")) }
  %w[train validation test].each do |split|
    members = category.fetch("families").select { |f| f.fetch("split") == split }
    total = category.fetch("split_totals").fetch(split)
    abort("Empty #{split} family set for #{category['label_id']}") if members.empty?
    base, extra = total.divmod(members.length)
    members.each_with_index { |f, i| f["planned_records"] = base + (i < extra ? 1 : 0) }
    abort("Zero quota in #{category['label_id']}/#{split}") if members.any? { |f| f.fetch("planned_records") <= 0 }
  end
  category["family_counts"] = %w[train validation test].to_h { |s| [s, category.fetch("families").count { |f| f.fetch("split") == s }] }
  family_decisions = family_rows.to_h { |f| [f.fetch("scenario_family_id"), f] }
  category.fetch("families").each do |f|
    source = family_decisions.fetch(f.fetch("scenario_family_id"))
    f["taxonomy_status"] = source.fetch("source_status").start_with?("既有") ? "approved_existing" : (source.fetch("decision") == "revise" ? "approved_revised_candidate" : "approved_candidate")
  end
end

manifest["total_split_records"] = { "train" => 700, "validation" => 150, "test" => 150 }
manifest["total_split_families"] = %w[train validation test].to_h { |s| [s, manifest.fetch("categories").sum { |c| c.fetch("family_counts").fetch(s) }] }
manifest["generation_gate"] = {
  "user_authorization" => "明確授權依助理獨立複核決定完成正式生成。",
  "pilot" => "保留 50 筆與 pending_manual_review；不併入、不計數。",
  "formal_records" => "每筆生成後設為 pending_manual_review。"
}
manifest.delete("draft_note")

# Validate every named group against the final assignments.
split_lookup = manifest.fetch("categories").flat_map { |c| c.fetch("families").map { |f| [f.fetch("scenario_family_id"), f.fetch("split")] } }.to_h
manifest.fetch("split_policy").fetch("related_family_groups").each do |g|
  missing_ids = g.fetch("scenario_family_ids") - split_lookup.keys
  abort("Group #{g['group_id']} includes inactive family IDs: #{missing_ids.join(', ')}") unless missing_ids.empty?
  splits = g.fetch("scenario_family_ids").map { |id| split_lookup.fetch(id) }.uniq
  abort("Group #{g['group_id']} crosses splits: #{splits.join(', ')}") unless splits == [g.fetch("split")]
end
manifest.fetch("categories").each do |c|
  %w[train validation test].each do |s|
    total = c.fetch("families").select { |f| f.fetch("split") == s }.sum { |f| f.fetch("planned_records") }
    abort("Bad quota #{c['label_id']}/#{s}: #{total}") unless total == c.fetch("split_totals").fetch(s)
  end
end
abort("Bad total quota") unless manifest.fetch("categories").sum { |c| c.fetch("families").sum { |f| f.fetch("planned_records") } } == 1000

plan = <<~MD
  # 正式 1,000 筆資料生成計畫 v1.3

  狀態：已依使用者指示採納助理獨立複核決定；taxonomy 與 split manifest 已另存正式版並凍結。正式資料生成於 2026-10-12 啟動，Pilot 保持獨立。

  ## 範圍與版本

  - 本次新增正式通話 **1,000 筆**，五類各 200 筆；Pilot v1.2.3 的 50 筆不計入，也不合併。
  - Pilot 來源：`pilot_v1.2.3.jsonl`。四筆逐字稿依採納決定修訂；Pilot 的 `review_status` 仍為 `pending_manual_review`。
  - 正式分類來源：`taxonomy_v1.3.yaml`；合併規則：`family_merge_map_v1.0.yaml`；已凍結切分：`formal_split_manifest_frozen_v1.0.yaml`。
  - 新版僅新增檔案；既有草案、Pilot、複核活頁簿與決定文件不覆寫。

  ## 固定資料規格

  - 固定角色 `R=客服`、`L=來電民眾`；客服先以中性問候開場，不在民眾說明前透露案件內容。
  - 每通使用 9、11 或 13 行多輪對話（符合 8–14 行範圍），至少 200 個中文字；包含民眾描述、客服追問、民眾補充與客服自然收尾。
  - 每筆只表達一個主要問題。客服只釐清與記錄，不替案件作實質回覆、不承諾處理或時程。
  - 使用自然臺灣繁體中文；輪替追問順序、對話長短、補充方式、自我修正和收尾。
  - 位置只保留行政區與公共空間類型；不放姓名、電話、門牌、精確地址、具名路口或可識別個資。
  - 每筆 `is_synthetic=true`、`review_status=pending_manual_review`，包含必要欄位：`id`、`transcript`、`label_id`、`label_name`、`scenario_id`、`scenario_family_id`、`split`、`speaker_map`、`generator_model`、`prompt_version`。

  ## 唯一 ID 與切分

  - ID 規則：`TPE1999-FORMAL-<CAT>-<SEQ4>`；情境 ID：`SCENARIO-FORMAL-<CAT>-<SEQ4>`。類別代碼 SW、RD、PK、WT、SC；各類序號 0001–0200。
  - 70/15/15 依類別配額為 train/validation/test 各 140/30/30，全體 700/150/150。每個家族完整放在單一 split；家族內逐家族整數配額已寫在凍結 manifest，皆大於 0。
  - 五類有效家族為 14／14／15／12／11，共 66。家族數分配為人行道 7/3/4、道路 7/3/4、公園 8/3/4、垃圾車 7/2/3、路面清潔 4/3/4。垃圾車調整是為讓「漏停／整段未服務／部分收運／停留過短」同在 train；validation 為 2 個家族，test 為 3 個家族。
  - 道路縱向轉換、局部隆起與廣域波狀起伏全部在 test；垃圾車國定假日與一般週末家族全部在 test。條件式 merge targets 依 manifest 所列群組固定同 split。

  ## 批次與續跑

  - 20 批、每批 50 筆。每筆在 `generation_manifest.csv` 預排 ID、label、family、split、批次與家族序號。
  - 每批原始輸出寫入 `raw_generated/batch_NNN.jsonl`。只有整批逐欄與對話檢查通過才寫入 `filtered_batches/batch_NNN.jsonl`；批次摘要、SHA-256、拒絕與重跑資訊記錄在 `batch_log.jsonl`。
  - `checkpoint.json` 每完成一批更新一次。失敗重跑沿用原 ID、scenario ID、label、family、split，增加 attempt 記錄；不覆寫先前失敗原始輸出。
  - 生成與驗證工具位於 `scripts/`。生成器使用固定種子及正式 taxonomy/manifest 作唯一來源。

  ## 最終驗收

  - 最終 JSONL 和 CSV 各恰 1,000 列；五類各 200，逐類 split 140/30/30，全體 split 700/150/150。
  - 驗證欄位、label-family 對照、ID 唯一、家族隔離、非零且精確配額、speaker map、9/11/13 行、中文字數、個資模式、類別名稱洩漏、完全重複與近似重複。
  - 不合格記錄留在原始批次，重生相同預排 ID，通過後才加入 filtered/final。人工逐筆複核仍需後續完成；AI/程式檢查不等同人工簽核。

  ## 版本差異與限制

  - v1.2 manifest 的公園 `label_name` 少了官方名稱中的「含車輛違規進入」；正式版改用 taxonomy 與 Pilot 一致的完整名稱。
  - v1.2 把四個收運事件標為同一 related group，卻分散在 train/validation；正式版讓四者同在 train，配額精確後垃圾車 split 家族數改為 7/2/3。validation/test 的家族樣本數有限，人工評估時需按家族檢視。
  - 本次沒有把 Pilot 改為人工通過，也沒有將生成資料的 `review_status` 設成通過。
MD

hashes = sources.transform_values { |p| Digest::SHA256.file(p).hexdigest }
report = <<~MD
  # 正式生成前檢查與凍結紀錄 v1.0

  日期：#{NOW}

  ## 來源核對

  | 檔案 | SHA-256 |
  |---|---|
  #{hashes.map { |name, hash| "| `#{name}` | `#{hash}` |" }.join("\n  ")}

  - Pilot v1.2.3：50 筆，五類各 10 筆，全部 `split=pilot` 且 `review_status=pending_manual_review`。
  - 與 v1.2.2 逐 ID 比對：只有 V12-037、038、048、050 的 `transcript` 欄改變；其餘 46 筆逐字稿與全部欄位不變。沒有標籤、scenario ID 或 family ID 變更。
  - 複核 XLSX 與獨立複核 Markdown 的建議一致：Pilot pass 46／revise 4／reject 0；家族 pass 48／revise 18／merge 9。家族 revise IDs 與 taxonomy v1.3 的修訂列一致；9 個 merge 來源皆不在 active taxonomy，所有目標均有效。
  - 活動家族數：人行道 14、道路 14、公園 15、垃圾車 12、路面清潔 11；共 66 個唯一 ID。

  ## 草案問題及處置

  - `formal_split_manifest_draft_v1.2.yaml` 中 `waste_stop_presence` 有 train 與 validation 兩種 split。正式版將該群組四個家族全置 train，並將垃圾車家族配置改為 7/2/3；每類資料筆數仍精確為 140/30/30。
  - v1.2 manifest 的 park `label_name` 為縮短版；正式版採 taxonomy v1.2.1 與 Pilot v1.2.3 的完整 canonical label。
  - WIND litter 條件分流在正式 merge map 明確分成「一般散落物／來源不明」、「確認果皮箱滿溢外漏」、「確認箱體破損外漏」。另兩項條件合併依可觀察主訴明確路由；不再有未處理條件路由。

  ## 凍結配置

  | 類別 | 家族數 train/validation/test | 筆數 train/validation/test |
  |---|---:|---:|
  #{manifest.fetch("categories").map { |c| "| #{c.fetch('label_name')} | #{%w[train validation test].map { |s| c.fetch('family_counts').fetch(s) }.join('/')} | 140/30/30 |" }.join("\n  ")}
  | **全體** | **#{manifest.fetch('total_split_families').values_at('train','validation','test').join('/')}** | **700/150/150** |

  - Pilot 50 筆完全獨立，不在上述配額內。正式 manifest 狀態 `frozen`。
  - 原始草案、Pilot、決定 workbook/Markdown 均保留，沒有覆寫或刪除。
MD

FileUtils.mkdir_p(OUT)
File.write(File.join(DATA, "taxonomy_v1.3.yaml"), YAML.dump(taxonomy, line_width: -1), mode: "w:UTF-8")
File.write(File.join(DATA, "family_merge_map_v1.0.yaml"), YAML.dump(merge_map, line_width: -1), mode: "w:UTF-8")
File.write(File.join(DATA, "formal_split_manifest_frozen_v1.0.yaml"), YAML.dump(manifest, line_width: -1), mode: "w:UTF-8")
File.write(File.join(DATA, "formal_generation_plan_v1.3.md"), plan, mode: "w:UTF-8")
File.write(File.join(OUT, "preflight_and_freeze_record_v1.0.md"), report, mode: "w:UTF-8")
puts JSON.pretty_generate({
  "taxonomy_family_counts" => counts,
  "merge_count" => merge_map.fetch("merges").length,
  "split_family_totals" => manifest.fetch("total_split_families"),
  "split_record_totals" => manifest.fetch("total_split_records"),
  "written" => outputs
})
