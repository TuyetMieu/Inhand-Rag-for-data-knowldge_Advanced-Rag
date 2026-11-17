"""Sửa dấu tiếng Việt cho văn bản OCR bằng từ vựng và ngữ cảnh cặp từ.

Chỉ thay một âm tiết bằng âm tiết khác có cùng mặt chữ khi bỏ dấu ("tu" -> "tư", "truờng" -> "trường"),
không thêm, bớt hay đổi chữ cái. Ứng viên được chấm bằng xác suất cặp từ (từ trước, từ sau) học từ
văn bản sạch, cộng một mức ưu tiên cho chữ OCR đọc được nếu chữ đó có trong từ vựng.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict

TOKEN = re.compile(r"[^\W\d_]+|[^\w]+|[\d_]+", re.UNICODE)
HORN, BREVE, CIRC = "̛", "̆", "̂"


def fold(s: str) -> str:
    """Bỏ toàn bộ dấu, đ -> d, viết thường."""
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _case_like(src: str, word: str) -> str:
    if src.isupper() and len(src) > 1:
        return word.upper()
    if src[:1].isupper():
        return word[:1].upper() + word[1:]
    return word


def _is_word(tok: str) -> bool:
    return tok[:1].isalpha()


class DiacriticCorrector:
    def __init__(self, texts: list[str], keep_bonus: float = 4.0, lam: float = 0.7, min_count: int = 2):
        """keep_bonus: log-odds ưu tiên giữ chữ OCR (nếu có trong từ vựng). lam: trọng số bigram.

        keep_bonus = 4 chọn theo scripts/eval_sua_dau.py: sửa được 98–99% lỗi dấu giả lập,
        sửa nhầm khoảng 0,2% âm tiết vốn đúng.
        """
        self.uni: Counter = Counter()
        self.bi: Counter = Counter()
        for t in texts:
            words = [w.lower() for w in TOKEN.findall(unicodedata.normalize("NFC", t)) if _is_word(w)]
            self.uni.update(words)
            self.bi.update(zip(words, words[1:]))
        self.total = sum(self.uni.values())
        self.cands: dict[str, list[str]] = defaultdict(list)
        for w, c in self.uni.items():
            if c >= min_count:
                self.cands[fold(w)].append(w)
        self.keep_bonus, self.lam = keep_bonus, lam
        # Thêm ưu tiên cho chữ OCR đã có dấu và có trong từ vựng: đổi dấu giữa hai từ hợp lệ ("tại"->"tài",
        # "mà"->"mã") hay sai. Đo trên OCR thật: mức 2 bỏ 45/58 lần sửa sai đã biết, mất 28/266 lần sửa đúng.
        self.marked_bonus = 2.0

    def _p_uni(self, w: str) -> float:
        return (self.uni.get(w, 0) + 0.1) / (self.total + 0.1 * len(self.uni))

    def _p_bi(self, a: str | None, b: str) -> float:
        if a is None or a not in self.uni:
            return self._p_uni(b)
        return self.lam * self.bi.get((a, b), 0) / self.uni[a] + (1 - self.lam) * self._p_uni(b)

    def _score(self, prev: str | None, w: str, nxt: str | None) -> float:
        s = math.log(self._p_bi(prev, w))
        if nxt is not None:
            s += math.log(self._p_bi(w, nxt))
        return s

    def correct(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        """Trả về văn bản đã sửa và danh sách (chữ cũ, chữ mới)."""
        toks = TOKEN.findall(unicodedata.normalize("NFC", text))
        widx = [i for i, t in enumerate(toks) if _is_word(t)]
        pre_changes = []
        for i in widx:
            # OCR hay đọc chữ "l" thường thành "I" hoa ("Năng Iực"); tiếng Việt không có từ bắt đầu bằng "I" + chữ thường.
            t = toks[i]
            if "I" in t and not t.isupper():
                v = t.replace("I", "l")
                if fold(v) in self.cands and fold(t) not in self.cands:
                    pre_changes.append((t, v))
                    toks[i] = v
        words = [toks[i].lower() for i in widx]
        out = list(words)
        changes = []
        for k, w in enumerate(words):
            cands = self.cands.get(fold(w))
            if not cands or (len(cands) == 1 and cands[0] == w):
                continue
            prev = out[k - 1] if k > 0 else None
            nxt = words[k + 1] if k + 1 < len(words) else None
            options = set(cands) | {w}
            if w != fold(w):
                # OCR làm rơi dấu chứ không tự thêm đủ dấu: chữ đã có dấu thì không đổi thành chữ không dấu
                # ("đầu tu" không thành "dau tu" chỉ vì nguồn học có đoạn gõ không dấu).
                options = {c for c in options if c != fold(c)}
            if w in self.uni:
                # Chữ OCR đã là từ hợp lệ: chỉ cân nhắc ứng viên có ngữ cảnh cặp từ thật trong nguồn học,
                # không đổi chỉ vì ứng viên phổ biến hơn ("cha đẻ" không thành "cha để").
                options = {c for c in options
                           if c == w or self.bi.get((prev, c), 0) + self.bi.get((c, nxt), 0) > 0}
                if options == {w}:
                    continue
            best, best_s = w, None
            keep = self.keep_bonus + (self.marked_bonus if w != fold(w) else 0.0)
            for c in options:
                s = self._score(prev, c, nxt) + (keep if c == w and w in self.uni else 0.0)
                if best_s is None or s > best_s:
                    best, best_s = c, s
            if best != w:
                out[k] = best
                changes.append((toks[widx[k]], _case_like(toks[widx[k]], best)))
        for k, i in enumerate(widx):
            if out[k] != words[k]:
                toks[i] = _case_like(toks[i], out[k])
        return "".join(toks), pre_changes + changes
