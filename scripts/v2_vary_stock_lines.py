#!/usr/bin/env python3
"""Assembly step for dataset v2.0.0 (ticket 25): vary repeated stock lines and template phrases.

The hand-written batches reuse a small set of agent stock lines (openers, "請問是哪一區？", closers)
and caller acknowledgements ("謝謝。"), plus a few label-correlated template phrases the audit
flagged as shortcuts. This script rewrites ONLY those lines/phrases; caller descriptions are untouched.

    python scripts/v2_vary_stock_lines.py            # backs up batches/ to batches_raw/ once, then rewrites batches/

Deterministic (fixed seed); re-running starts again from batches_raw/.
"""

from __future__ import annotations

import random
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v2_dataset_tools as t  # noqa: E402

RAW = t.V2 / "batches_raw"
SEED = 20261114

GREETINGS = ["市民專線您好", "1999您好", "臺北市1999您好", "您好，這裡是1999", "您好，這裡是臺北市1999",
             "您好，1999市民熱線", "1999市民熱線您好", "您好，市民專線", "臺北1999，您好", "這裡是1999，您好",
             "您好，臺北市民當家熱線", "臺北市民當家熱線您好", "您好，1999專線", "1999專線您好", "您好，這邊是1999",
             "這邊是臺北市1999，您好"]
OPEN_PROMPTS = ["請問有什麼需要協助的？", "請說。", "請問要反映什麼狀況？", "請問有什麼事情需要幫忙？", "請問您今天要反映什麼？",
                "請問有什麼我可以幫您的？", "請問是什麼事情呢？", "方便說明一下狀況嗎？", "請問您遇到什麼問題？", "請問要通報什麼？",
                "我在聽，請說。", "請問您想反映什麼事？", "請問有什麼狀況？", "請問需要什麼服務？", "請問有什麼要告訴我們的？",
                "請問今天有什麼事？", "請問您打來是要反映什麼？", "請問有什麼需要處理的情況？", "請問您要反映哪方面的問題？", "請講，我在線上。",
                "有什麼可以為您服務的？", "請問發生什麼事了？", "請問您需要反映什麼？", "請問有什麼要通報的？", "請問有什麼問題需要協助？",
                "請問您今天打來是什麼事？", "請問想詢問還是反映事情？", "請問我能幫您什麼？", "請問有什麼情況要說明？", "請問您碰到什麼狀況？",
                "請問是要反映什麼呢？", "請直接說，我幫您記錄。", "請問您想通報什麼？", "請問今天要協助什麼？", "請問有什麼事要反映？",
                "請問要跟我們說什麼？", "請問有什麼困擾嗎？", "請問您那邊有什麼狀況？", "請問有什麼事情？", "請問您要找我們反映什麼？",
                "請問需要幫您什麼？", "請問有什麼要提出的？", "請問您遇到了什麼？", "請問有什麼要麻煩我們的？", "請問有什麼要協助的地方？",
                "請問是什麼問題呢？", "請問有什麼事需要反映？", "請說明您的狀況。", "請問您要說的是什麼事？", "請問今天有什麼需要？",
                "請問有什麼狀況要回報？", "請問您需要什麼協助？", "請問有什麼話要轉達？", "請問有哪裡需要幫忙？", "請問什麼事情呢？",
                "請問您有什麼需要？", "請問您要反映的是？", "請問您這通電話是要？", "請問有什麼要處理？", "請問您有什麼事？",
                "請問您想說明什麼？", "請問有什麼要我們知道的？", "請問您今天的問題是？", "請問您要反映什麼情形？"]
LOC_PREFIX = ["", "好的，", "了解，", "好，", "嗯，", "明白，", "收到，", "那", "先確認一下，", "麻煩您，"]
LOC_CORE = ["請問在哪一區？", "請問是哪一區呢？", "地點在哪裡呢？", "請問大概在什麼位置？", "方便說一下地點嗎？", "請問是哪個行政區？",
            "請問位置在哪裡？", "在哪一區、哪一帶呢？", "請問那邊是哪一區？", "可以告訴我地點嗎？", "請問是在哪裡？", "請問大概在哪一帶？",
            "地點方便描述一下嗎？", "請問是在哪個區域？", "那個地方在哪一區？", "請說一下大概位置。", "請問那是在什麼地方？", "位置大概在哪裡呢？",
            "請問是哪一區的哪一帶？", "請問在哪個地方？", "您方便說是哪一區嗎？", "請問是在什麼位置？", "麻煩說一下地點。", "地點在哪一區呢？",
            "請問那裡屬於哪一區？", "可以說一下是哪一帶嗎？", "請問具體在哪？", "請問大概的位置？", "請問所在位置是？", "請問是發生在哪裡？",
            "您說的地方是在哪一區？", "請問地點大概在哪一帶？", "可以說一下附近的路名嗎？", "請問附近有什麼明顯的地方嗎？", "請問那一帶是哪一區？",
            "請問在哪一帶呢？", "地點是哪裡？", "請問哪一區？", "那裡是哪一區呢？", "請問是在哪一帶？"]
AGENT_THANKS = ["謝謝您的反映。", "不客氣。", "收到，謝謝您。", "多謝您通報。", "不客氣，謝謝您打來。", "謝謝您告訴我們。", "好的，謝謝您來電。",
                "不會，謝謝您。", "謝謝您特地打來。", "感謝您的通報。", "謝謝，祝您順心。", "好的，不客氣。", "謝謝您的耐心。", "謝謝您提供的資訊。",
                "不客氣，再見。", "謝謝您，再見。", "好，謝謝您的說明。", "謝謝您留意這件事。", "感謝您撥空反映。", "謝謝您，辛苦了。",
                "謝謝來電。", "不客氣，有需要再打來。", "感謝您的細心。", "謝謝您幫忙注意。", "好的，感謝。"]
CALLER_THANKS = ["謝謝。", "謝謝你。", "好，謝謝。", "好，謝謝你。", "謝謝，拜託了。", "謝謝，麻煩了。", "好，麻煩你了。", "感謝。", "謝謝喔。",
                 "好，感謝。", "嗯，謝謝。", "好的，謝謝。", "那就麻煩你們了。", "好，拜託了。", "謝啦。", "OK，謝謝。", "好喔，謝謝。",
                 "那先這樣，謝謝。", "好，那麻煩了。", "感謝你。", "謝謝，再見。", "好，掰掰。", "辛苦了，謝謝。", "好，就這樣，謝謝。",
                 "謝謝你們。", "好，那拜託了。", "嗯，好，謝謝。", "好的，麻煩了。", "謝謝，辛苦了。", "那就拜託你了。"]
CALLER_CONFIRM = ["對。", "對，謝謝。", "對，就是這樣。", "對，就是那樣。", "對，麻煩了。", "沒錯。", "是的。", "對對對。", "嗯，對。",
                  "沒錯，就是這樣。", "對，就是那裡。", "嗯，沒錯。", "對，你講得對。", "是，就是這樣。", "對，大概就是這樣。", "嗯嗯，對。"]
TW_THANKS = ["多謝喔。", "多謝。", "感謝喔。", "勞力喔。", "真多謝。", "多謝你。", "好，多謝。", "按呢就好，多謝。", "麻煩你矣。", "拜託你矣。"]

STOCK_LOCATION = {"請問是哪一區？", "請問是哪一區的公園？", "請問在哪裡？", "請問是哪一條路？", "請問在哪裡呢？", "好的，請問是哪一區？",
                  "請問您住在哪一區？", "請問是哪一區的河濱公園？", "請問在哪一區？", "好的，請問在哪裡？", "請問在哪一條路？",
                  "請問是哪一區、哪個停靠點？", "請問是在哪裡？", "好的，請問是哪一區的公園？", "請問您住在哪一區、哪個停靠點附近？",
                  "請問是哪一區、哪一條路？", "請問是哪一區、哪個停靠點附近？", "請問是哪一區、大概哪個位置？", "請問在哪一段路？", "請問在哪一段路呢？",
                  "請問是在哪裡呢？", "請問是哪一區的公園、哪個入口？", "請問在哪裡呢？"}
STOCK_AGENT_THANKS = {"謝謝您的反映。", "不客氣。", "收到，謝謝您。", "多謝您通報。", "不客氣，謝謝您打來。", "謝謝您告訴我們。",
                      "謝謝您打來。", "謝謝您的詢問。", "謝謝您主動反映。", "不客氣，謝謝您。"}
STOCK_CALLER_THANKS = {"謝謝。", "謝謝你。", "好，謝謝。", "謝謝，拜託了。", "好，謝謝你。", "謝謝你們。", "好的，謝謝。", "好，謝謝你。"}
STOCK_CALLER_CONFIRM = {"對。", "對，謝謝。", "對，就是這樣。", "對，就是那樣。", "對，麻煩了。"}
STOCK_TW = {"多謝喔。", "多謝。", "好，多謝。"}
DIRECTION_ALTS = ["往{}那邊，", "往{}去，", "朝{}那頭，", "往{}的方向，", "往{}那一側，"]
RANGE_ALTS = ["公尺範圍", "公尺內", "公尺一帶", "公尺左右的地方", "公尺的區域"]
BIN_ALTS = ["公共垃圾桶", "垃圾桶", "路邊垃圾桶", "果皮箱", "公共垃圾桶"]
STOP_ALTS = ["停靠點", "停靠處", "停靠位置", "丟垃圾的地點", "收垃圾的位置"]
PARK_NEAR_ALTS = ["附近公園", "一帶的公園", "旁的公園", "周邊的公園", "附近的公園"]
PARK_ONE_ALTS = ["的一個公園", "的公園", "那個公園", "旁邊的公園", "附近的小公園", "那邊的公園"]
SEG_ALTS = ["段往", "段朝", "段、往", "段向"]
SW_DONE_ALTS = ["。我已經", "，我已經", "。這邊已經", "。我這邊已經", "。已經幫您"]
ACK = ["", "好，", "嗯，", "了解，", "那", "好的，", "明白，"]
STOCK_QUESTIONS = {
    "範圍大概多大？": ["範圍大概多大？", "大概多大一片？", "範圍有多廣？", "大概占了多大的面積？", "面積大概多少？", "大概延伸多大？"],
    "這個情況大概多久了？": ["這個情況大概多久了？", "這樣大概多久了？", "大概持續多久了？", "從什麼時候開始的？", "多久以前就這樣了？", "您注意到多久了？"],
    "大概多久了？": ["大概多久了？", "持續多久了？", "從什麼時候開始？", "這樣多久了？"],
    "垃圾桶本身正常嗎？": ["垃圾桶本身正常嗎？", "桶子本身有沒有壞？", "垃圾桶有沒有破損？", "桶子是好的嗎？", "箱體本身沒問題嗎？"],
    "菸蒂的範圍大概多大？": ["菸蒂的範圍大概多大？", "菸蒂大概散多大一片？", "菸蒂集中的範圍多大？", "菸蒂大概分布多廣？"],
    "散落的範圍大概多大？": ["散落的範圍大概多大？", "大概散了多大一片？", "散開的範圍多大？", "大概散到多遠？"],
    "那段人行道平常走的人多嗎？": ["那段人行道平常走的人多嗎？", "那邊平常行人多嗎？", "那段路人多不多？", "平常經過那裡的人多嗎？", "那裡行人來往多嗎？"],
    "請問是哪個路口？": ["請問是哪個路口？", "是哪兩條路的路口？", "路口是哪裡呢？", "哪一個路口呢？", "請問路口在哪？"],
    "請問在哪個路口？": ["請問在哪個路口？", "是在哪個交叉口？", "路口在哪裡？", "哪兩條路交叉的地方？"],
    "請問是哪一站？": ["請問是哪一站？", "是哪個站牌？", "哪一站呢？", "站名是？", "是在哪個公車站？"],
    "請問學校在哪裡？": ["請問學校在哪裡？", "學校在哪一區？", "是哪一帶的學校？", "學校大概在哪？"],
    "那段大概多長？": ["那段大概多長？", "大概延伸多長？", "長度大概多少？", "那一段有多長？"],
    "深度大概多少？": ["深度大概多少？", "大概有多深？", "深度呢？", "凹下去多深？"],
    "大概多少？": ["大概多少？", "數量大概多少？", "大約有多少？", "大概有幾個？"],
    "請問是哪一條路？": ["請問是哪一條路？", "是哪條路呢？", "路名是？", "在哪一條路上？"],
}
CALLER_ACK = ["", "好，", "嗯，", "喔，", "那", "好的，", "OK，"]
CALLER_CORE = ["謝謝", "謝謝你", "感謝", "麻煩了", "拜託了", "謝謝喔", "辛苦了", "麻煩你們了", "謝謝，再見", "就先這樣，謝謝", "謝謝，掰掰", "感謝你們"]


class Pool:
    """Draw variants with a per-variant cap, cycling a shuffled order."""

    def __init__(self, items: list[str], rng: random.Random, cap: int):
        self.items, self.rng, self.cap = list(items), rng, cap
        self.used: dict[str, int] = {}
        self.rng.shuffle(self.items)
        self.i = 0

    def draw(self, avoid: set[str] = frozenset()) -> str:
        for _ in range(len(self.items) * 2):
            cand = self.items[self.i % len(self.items)]
            self.i += 1
            if self.used.get(cand, 0) < self.cap and cand not in avoid:
                self.used[cand] = self.used.get(cand, 0) + 1
                return cand
        cand = self.rng.choice(self.items)
        self.used[cand] = self.used.get(cand, 0) + 1
        return cand


def cjk(lines: list[str]) -> int:
    return len(t.CJK.findall("\n".join(lines)))


def vary(records: list[dict], label_of: dict[str, str]) -> list[dict]:
    rng = random.Random(SEED)
    openers = Pool([g + "，" + p for g in GREETINGS for p in OPEN_PROMPTS], rng, 1)
    locs = Pool([p + c for p in LOC_PREFIX for c in LOC_CORE], rng, 2)
    athanks = Pool(AGENT_THANKS, rng, 40)
    cthanks = Pool([a + c + "。" for a in CALLER_ACK for c in CALLER_CORE], rng, 6)
    cconfirm = Pool(CALLER_CONFIRM, rng, 25)
    tw = Pool(TW_THANKS, rng, 12)
    qpools = {k: Pool([a + v for a in ACK for v in vs], rng, 2) for k, vs in STOCK_QUESTIONS.items()}
    out = []
    for rec in records:
        label = label_of[rec["id"]]
        lines = list(rec["lines"])
        # 1) opener: first agent line, unless it carries Taiwanese (keep the code-switch intact)
        if lines[0].startswith("R:"):
            lines[0] = "R:" + openers.draw()
        for i in range(1, len(lines)):
            sp, body = lines[i][:2], lines[i][2:]
            if sp == "R:" and body in STOCK_LOCATION:
                lines[i] = "R:" + locs.draw()
            elif sp == "R:" and body in STOCK_AGENT_THANKS:
                lines[i] = "R:" + athanks.draw()
            elif sp == "L:" and body in STOCK_CALLER_THANKS:
                lines[i] = "L:" + cthanks.draw()
            elif sp == "L:" and body in STOCK_CALLER_CONFIRM:
                lines[i] = "L:" + cconfirm.draw()
            elif sp == "L:" and body in STOCK_TW:
                lines[i] = "L:" + tw.draw()
            elif sp == "R:" and body in qpools:
                lines[i] = "R:" + qpools[body].draw()
        # 2) label-correlated template phrases flagged by the shortcut audit
        for i, ln in enumerate(lines):
            if label == "road_surface_defect" and ln.startswith("L:"):
                ln = re.sub(r"往([^，。、\s]{1,10}?)的方向，", lambda m: rng.choice(DIRECTION_ALTS).format(m.group(1)), ln)
            if label == "street_cleaning" and ln.startswith("R:"):
                ln = re.sub("公尺範圍", lambda m: rng.choice(RANGE_ALTS), ln)
                ln = re.sub("公共垃圾桶", lambda m: rng.choice(BIN_ALTS), ln)
            if label == "waste_truck_service" and ln.startswith("R:"):
                ln = re.sub("停靠點", lambda m: rng.choice(STOP_ALTS), ln)
            if label == "park_general_maintenance":
                if ln.startswith("R:"):
                    ln = re.sub("附近公園", lambda m: rng.choice(PARK_NEAR_ALTS), ln)
                else:
                    ln = re.sub("的一個公園", lambda m: rng.choice(PARK_ONE_ALTS), ln)
            if label == "road_surface_defect":
                ln = re.sub("段，?往", lambda m: rng.choice(SEG_ALTS), ln)
            if label == "sidewalk_maintenance" and ln.startswith("R:"):
                ln = re.sub("。我已經", lambda m: rng.choice(SW_DONE_ALTS), ln)
            lines[i] = ln
        # 3) drop a trailing bare caller "thanks" line (or trailing thanks + stock agent reply) when the
        #    call stays within the length rules: real calls often end on the agent's confirmation.
        tail_l = {"L:" + x for x in CALLER_THANKS + CALLER_CONFIRM + TW_THANKS + cthanks.items}
        tail_r = {"R:" + x for x in AGENT_THANKS}
        if rng.random() < 0.55:
            cut = 0
            if lines[-1] in tail_l:
                cut = 1
            elif len(lines) >= 2 and lines[-1] in tail_r and lines[-2] in tail_l:
                cut = 2
            if cut and len(lines) - cut >= t.MIN_LINES and cjk(lines[:-cut]) >= t.MIN_CHARS:
                lines = lines[:-cut]
        if cjk(lines) < t.MIN_CHARS:  # a shorter stock variant pushed it under the floor: keep the original wording
            lines = list(rec["lines"])
        out.append({**rec, "lines": lines, "transcript": "\n".join(lines)})
    return out


def write_batches(records: list[dict]) -> None:
    by_src: dict[str, list[dict]] = {}
    for r in records:
        by_src.setdefault(r["source"], []).append(r)
    for src, recs in by_src.items():
        text = "".join(f"### {r['id']}|{r['family']}\n" + "\n".join(r["lines"]) + "\n" for r in recs)
        (t.BATCHES / src).write_text(text, encoding="utf-8")


def main() -> int:
    if not RAW.exists():
        shutil.copytree(t.BATCHES, RAW)
        print(f"backed up raw batches to {RAW}")
    records = []
    for p in sorted(RAW.glob("batch_*.txt")):
        records += t.parse_file(p)
    plan = {r["id"]: r for b in __import__("json").loads(t.PLAN.read_text(encoding="utf-8"))["batches"] for r in b}
    label_of = {rid: rec["label_id"] for rid, rec in plan.items()}
    varied = vary(records, label_of)
    write_batches(varied)
    changed = sum(a["lines"] != b["lines"] for a, b in zip(records, varied))
    print(f"varied {changed}/{len(records)} records")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
