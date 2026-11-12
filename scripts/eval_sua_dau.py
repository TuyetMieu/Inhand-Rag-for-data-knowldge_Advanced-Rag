"""Đo bộ sửa dấu trên văn bản sạch bị làm hỏng giả lập theo kiểu lỗi của OCR.

Học từ vựng trên các văn bản huấn luyện, thử trên một luật để riêng (không có trong huấn luyện):
- bỏ móc ư/ơ (giữ dấu thanh) với xác suất p_moc, như OCR thật: "được" -> "đuợc", "tư" -> "tu";
- đổi dấu thanh với xác suất p_thanh: "phủ" -> "phù".
Báo tỷ lệ âm tiết sai trước/sau khi sửa và tỷ lệ sửa nhầm âm tiết vốn đúng.

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/eval_sua_dau.py
"""
import json
import random
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from inhand_rag.ingest.sua_dau import TOKEN, DiacriticCorrector, _is_word  # noqa: E402

TONES = ["́", "̀", "̉", "̃", "̣"]


def corrupt(word: str, rng: random.Random, p_moc: float, p_thanh: float) -> str:
    d = unicodedata.normalize("NFD", word)
    if "̛" in d and rng.random() < p_moc:
        d = d.replace("̛", "")
    tones = [c for c in d if c in TONES]
    if tones and rng.random() < p_thanh:
        # Bỏ dấu thanh cũ rồi đặt dấu mới ngay sau toàn bộ dấu phụ của nguyên âm đó (sau mũ/móc),
        # để ký tự luôn ghép được như văn bản OCR thật.
        i = d.index(tones[0])
        base = i
        while base > 0 and unicodedata.combining(d[base]):
            base -= 1
        end = base + 1
        while end < len(d) and unicodedata.combining(d[end]):
            end += 1
        cluster = "".join(c for c in d[base:end] if c not in TONES)
        new = rng.choice([t for t in TONES if t != tones[0]] + [""])
        d = d[:base] + cluster + new + d[end:]
    return unicodedata.normalize("NFC", d)


def run(train: list[str], test: str, p_moc: float, p_thanh: float, keep_bonus: float, seed: int = 0):
    corr = DiacriticCorrector(train, keep_bonus=keep_bonus)
    rng = random.Random(seed)
    toks = TOKEN.findall(test)
    noisy = [corrupt(t, rng, p_moc, p_thanh) if _is_word(t) else t for t in toks]
    fixed, _ = corr.correct("".join(noisy))
    gold = [t.lower() for t in toks if _is_word(t)]
    bad = [t.lower() for t in noisy if _is_word(t)]
    out = [t.lower() for t in TOKEN.findall(fixed) if _is_word(t)]
    assert len(gold) == len(bad) == len(out)
    err_before = sum(g != b for g, b in zip(gold, bad))
    err_after = sum(g != o for g, o in zip(gold, out))
    clean = [(g, o) for g, b, o in zip(gold, bad, out) if g == b]
    broken_clean = sum(g != o for g, o in clean)
    return len(gold), err_before, err_after, broken_clean, len(clean)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    from inhand_rag.ingest.corpus import build

    chunks = [json.loads(l) for l in (ROOT / "data" / "luat" / "chunks.jsonl").open(encoding="utf-8")]
    test_law = "LKDBDS-2023"
    test_texts = {c["text"] for c in chunks if c["van_ban"] == test_law}
    test = "\n".join(c["text"] for c in chunks if c["van_ban"] == test_law)
    # Cùng nguồn học như khi sửa OCR thật (luật + docx), trừ chính luật dùng để thử.
    train = [t for t in build([]) if t not in test_texts]
    print("Học trên %d văn bản (luật khác + docx); thử trên %s (%d ký tự)" % (len(train), test_law, len(test)))
    print("Lưu ý: các docx có thể trích lại vài điều của %s, nên kết quả có thể hơi lạc quan." % test_law)
    print("%-34s %8s %10s %10s %14s" % ("Kịch bản", "âm tiết", "sai trước", "sai sau", "sửa nhầm"))
    for p_moc, p_thanh in [(0.2, 0.0), (0.2, 0.02), (0.4, 0.05)]:
        for kb in (3.0, 4.0, 5.0):
            n, eb, ea, bc, nc = run(train, test, p_moc, p_thanh, kb)
            print("móc %.0f%%, thanh %.0f%%, ưu tiên %.1f   %8d %9.2f%% %9.2f%% %13.3f%%"
                  % (100 * p_moc, 100 * p_thanh, kb, n, 100 * eb / n, 100 * ea / n, 100 * bc / nc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
