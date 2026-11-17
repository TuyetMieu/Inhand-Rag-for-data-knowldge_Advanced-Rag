"""Tách hồ sơ docx (theo manifest.json) thành chunk cha–con có tiêu đề ngữ cảnh.

Đọc thẳng word/document.xml theo đúng thứ tự đoạn văn và bảng (không cần Docling: với docx, Docling
cũng chỉ đọc XML này, mà kéo theo rất nhiều thư viện). Bảng chuyển thành Markdown, mỗi hàng một dòng.

- Mục: tách tại đoạn tiêu đề (style Title/Heading, cả đoạn in đậm, chữ in hoa, hoặc "Điều N", "I.", "1.").
- Chunk con: một phần của mục, tối đa CHILD_MAX ký tự; bảng dài cắt theo hàng, lặp lại hàng tiêu đề.
- Chunk cha: cả mục (tối đa PARENT_MAX ký tự), để đưa cho LLM đọc đủ ngữ cảnh.
- Tiêu đề ngữ cảnh: "KH002 › Giai đoạn 2 › Đợt 3 › <tên tài liệu> › <mục>".

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python -m inhand_rag.ingest.hoso data\\hoso\\KH002 data\\hoso
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CHILD_MAX = 1200
PARENT_MAX = 4000
STAGE = {1: "Giai đoạn 1 – Giữ chỗ và đặt cọc", 2: "Giai đoạn 2 – Ký hợp đồng mua bán",
         3: "Giai đoạn 3 – Thanh toán theo đợt", 4: "Giai đoạn 4 – Bàn giao", 5: "Giai đoạn 5 – Cấp giấy chứng nhận"}
RE_HEAD = re.compile(r"^(Điều\s+\d+|[IVX]{1,4}\.|PHẦN\b|Mục\s+\d+|\d{1,2}\.\s|[A-Z]\.\s)")


def _text(el) -> str:
    out = []
    for n in el.iter():
        if n.tag == W + "t" and n.text:
            out.append(n.text)
        elif n.tag in (W + "tab",):
            out.append(" ")
        elif n.tag in (W + "br", W + "cr"):
            out.append("\n")
    return unicodedata.normalize("NFC", "".join(out)).strip()


def _is_heading(p, text: str) -> bool:
    if not text or len(text) > 120:
        return False
    st = p.find(f"{W}pPr/{W}pStyle")
    if st is not None and re.match(r"(Title|Heading|Tieude|TOC)", st.get(W + "val", ""), re.I):
        return True
    runs = [r for r in p.iter(W + "r") if _text(r)]
    bold = runs and all((b := r.find(f"{W}rPr/{W}b")) is not None and b.get(W + "val", "1") not in ("0", "false")
                        for r in runs)
    letters = [c for c in text if c.isalpha()]
    upper = len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) > 0.8
    return bool(bold or upper or (RE_HEAD.match(text) and len(text) < 90 and not text.endswith((".", ";", ","))))


def _table(tbl) -> list[str]:
    rows = []
    for tr in tbl.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            vm = tc.find(f"{W}tcPr/{W}vMerge")
            if vm is not None and vm.get(W + "val") is None:  # ô gộp dọc nối tiếp: để trống
                cells.append("")
                continue
            cells.append(re.sub(r"\s+", " ", " ".join(_text(p) for p in tc.iter(W + "p"))).strip().replace("|", "/"))
        if any(cells):
            rows.append("| " + " | ".join(cells) + " |")
    return rows


def blocks(path: Path) -> list[tuple[str, str]]:
    """Trả về các khối theo thứ tự: ("h", tiêu đề), ("p", đoạn), ("t", bảng Markdown)."""
    body = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml")).find(W + "body")
    out = []
    for el in body:
        if el.tag == W + "p":
            t = _text(el)
            if t:
                out.append(("h" if _is_heading(el, t) else "p", t))
        elif el.tag == W + "tbl":
            rows = _table(el)
            if rows:
                out.append(("t", "\n".join(rows)))
    return out


def sections(bl: list[tuple[str, str]]) -> list[tuple[str, list[tuple[str, str]]]]:
    """Gom khối thành mục; các tiêu đề liền nhau gộp thành một tiêu đề."""
    secs, head, cur = [], "", []
    for kind, t in bl:
        if kind == "h":
            if cur:
                secs.append((head, cur))
                head, cur = t, []
            else:
                head = (head + " / " + t) if head else t
        else:
            cur.append((kind, t))
    if cur or head:
        secs.append((head, cur))
    return secs


def _split_table(t: str) -> list[str]:
    rows = t.split("\n")
    if len(t) <= CHILD_MAX or len(rows) < 3:
        return [t]
    head, out, buf = rows[0], [], []
    for r in rows[1:]:
        if buf and len(head) + sum(len(x) + 1 for x in buf) + len(r) > CHILD_MAX:
            out.append("\n".join([head] + buf))
            buf = []
        buf.append(r)
    if buf:
        out.append("\n".join([head] + buf))
    return out


def children(content: list[tuple[str, str]]) -> list[str]:
    """Chia nội dung một mục thành chunk con: đoạn văn gom tới CHILD_MAX, bảng cắt theo hàng."""
    out, buf = [], ""
    for kind, t in content:
        pieces = _split_table(t) if kind == "t" else [t]
        for piece in pieces:
            if kind == "t" and len(piece) > CHILD_MAX // 2:
                if buf:
                    out.append(buf)
                    buf = ""
                out.append(piece)
            elif buf and len(buf) + 1 + len(piece) > CHILD_MAX:
                out.append(buf)
                buf = piece
            else:
                buf = (buf + "\n" + piece) if buf else piece
    if buf:
        out.append(buf)
    return out


def build(hoso_dir: Path) -> tuple[list[dict], list[dict], list[str]]:
    m = json.loads((hoso_dir / "manifest.json").read_text(encoding="utf-8"))
    ma = m["ma_ho_so"]
    parents, chunks, notes = [], [], []
    for doc in m["tai_lieu"]:
        path = hoso_dir / doc["file"]
        if not path.exists():
            notes.append("thiếu file %s" % doc["file"])
            continue
        crumbs = [ma, STAGE.get(doc["stage"], "Giai đoạn %s" % doc["stage"])]
        if doc.get("tranche"):
            crumbs.append("Đợt %s" % doc["tranche"])
        crumbs.append(doc["title"])
        meta = {"ma_ho_so": ma, "doc_id": doc["id"], "doc_type": doc["doc_type"], "title": doc["title"],
                "stage": doc["stage"], "tranche": doc.get("tranche"), "branch": doc.get("branch"),
                "date": doc.get("date"), "required": doc.get("required"), "status": doc.get("status"),
                "file": doc["file"]}
        # Đơn vị = (tên mục, phần nội dung kèm tên mục). Mục ngắn liền nhau ("Bên A", "Điều 2: Thời hạn")
        # được gộp thành một chunk con tới CHILD_MAX.
        kids: list[tuple[str, str]] = []
        for head, content in sections(blocks(path)):
            pieces = children(content) or [""]
            for p in pieces:
                text = "\n".join(x for x in (head, p) if x)
                if kids and len(kids[-1][1]) + 1 + len(text) <= CHILD_MAX and (len(text) < 400 or len(kids[-1][1]) < 400):
                    kids[-1] = (kids[-1][0], kids[-1][1] + "\n" + text)
                else:
                    kids.append((head, text))
        # Chunk cha = các chunk con liền nhau, tối đa PARENT_MAX ký tự (tài liệu ngắn thì cha là cả tài liệu).
        groups, g = [], []
        for k in kids:
            if g and sum(len(x[1]) for x in g) + len(k[1]) > PARENT_MAX:
                groups.append(g)
                g = []
            g.append(k)
        if g:
            groups.append(g)
        for gi, grp in enumerate(groups, start=1):
            pid = "%s-P%d" % (doc["id"], gi)
            parents.append({**meta, "id": pid, "vi_tri": " › ".join(crumbs), "phan": "%d/%d" % (gi, len(groups)),
                            "text": "\n".join(x[1] for x in grp)})
            for ci, (head, text) in enumerate(grp, start=1):
                show = head and head != doc["title"] and not head.upper().startswith("CỘNG HÒA")
                vi_tri = " › ".join(crumbs + ([head] if show else []))
                chunks.append({**meta, "id": "%s-C%d" % (pid, ci), "parent_id": pid, "vi_tri": vi_tri,
                               "text": text, "co_bang": text.startswith("|") or "\n|" in text})
    return parents, chunks, notes


def main(hoso_dir: str, out_dir: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parents, chunks, notes = build(Path(hoso_dir))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    name = Path(hoso_dir).name.lower()
    for fname, rows in (("%s_parents.jsonl" % name, parents), ("%s_chunks.jsonl" % name, chunks)):
        with (out / fname).open("w", encoding="utf-8") as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    lens = sorted(len(c["text"]) for c in chunks)
    docs = len({c["doc_id"] for c in chunks})
    print("%d tài liệu -> %d chunk cha, %d chunk con (%d có bảng)" % (docs, len(parents), len(chunks),
                                                                      sum(c["co_bang"] for c in chunks)))
    print("độ dài chunk con: trung vị %d, lớn nhất %d ký tự" % (lens[len(lens) // 2], lens[-1]))
    for n in notes:
        print("VẤN ĐỀ:", n)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
