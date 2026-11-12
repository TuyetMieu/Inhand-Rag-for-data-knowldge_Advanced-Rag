"""Tách các luật dạng PDF có text thành Điều (chunk cha) và Khoản (chunk con).

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python -m inhand_rag.ingest.luat "..\\Dataset Luật" data\\luat

Đọc schemas/luat_catalog.csv, lấy các văn bản `pdf_text`, ghép các phần Công báo theo thứ tự,
lọc header/chữ ký số, nhận đề mục Phần/Chương/Mục/Điều/Khoản theo đầu dòng.
Ghi data/luat/dieu.jsonl (mỗi Điều một dòng) và data/luat/chunks.jsonl (mỗi Khoản một dòng),
kèm báo cáo kiểm tra (Điều có liên tục không, Khoản có liên tục không).
"""
from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[3]

# Các khoản bị Luật 43/2024/QH15 sửa đổi: (mã văn bản, Điều, Khoản) -> (Điều của L43, nội dung mới)
SUA_DOI = {
    ("LKDBDS-2023", 82, 1): ("L43-2024 Điều 3", "Luật này có hiệu lực thi hành từ ngày 01 tháng 8 năm 2024."),
    ("LNO-2023", 197, 1): ("L43-2024 Điều 2", "Luật này có hiệu lực thi hành từ ngày 01 tháng 8 năm 2024."),
    ("LDD-2024", 252, 1): ("L43-2024 Điều 1 khoản 2", "Luật này có hiệu lực thi hành từ ngày 01 tháng 8 năm 2024, "
                           "trừ trường hợp quy định tại khoản 2 và khoản 3 Điều này."),
    ("LDD-2024", 251, 2): ("L43-2024 Điều 1 khoản 1", None),
    ("LDD-2024", 255, 10): ("L43-2024 Điều 1 khoản 3", None),
    ("LDD-2024", 260, 4): ("L43-2024 Điều 1 khoản 4 (khổ đầu)", None),
}

DROP = [
    re.compile(r"^\d{1,4}$"),                                   # số trang
    re.compile(r"^\d*\s*CÔNG BÁO/Số"),                          # header Công báo
    re.compile(r"^(Người ký|Email|Cơ quan|Thời gian ký):"),     # chữ ký số
]
RE_PHAN = re.compile(r"^Phần thứ\s+\S+", re.I)
RE_CHUONG = re.compile(r"^Chương\s+([IVXLC]+)\b")
RE_MUC = re.compile(r"^Mục\s+(\d+)\b")
RE_DIEU = re.compile(r"^Điều\s+(\d+)\.\s*(.*)$")
RE_KHOAN = re.compile(r"^(\d{1,3})\.\s+(.*)$")
RE_DIEM = re.compile(r"^([a-zđ])\)\s+")
RE_END = re.compile(r"^Luật này (đã )?được Quốc hội")
MAX_CHUNK = 3000


@dataclass
class Dieu:
    so: int
    tieu_de: str
    trang: int
    chuong: str = ""
    muc: str = ""
    mo_dau: list[str] = field(default_factory=list)
    khoan: list[dict] = field(default_factory=list)
    phu_luc: str = ""  # chỉ ở Điều cuối của bản OCR: phần sau "Nơi nhận:" (phụ lục, mẫu biểu)
    trang_phu_luc: int = 0
    tep: int = 1  # bản OCR: số thứ tự file chứa đề mục Điều (văn bản chia nhiều file)


def read_lines(base: Path, files: list[str]) -> list[tuple[str, int]]:
    """Trả về các dòng đã lọc kèm số trang trong file (đánh số từ 1, theo từng phần)."""
    out = []
    for part, f in enumerate(files):
        doc = pymupdf.open(base / f)
        for pno, page in enumerate(doc, start=1):
            lines = [l.strip() for l in page.get_text().split("\n")]
            lines = [l for l in lines if l and not any(p.search(l) for p in DROP)]
            if part > 0 and pno == 1:
                # Bỏ phần đầu của số Công báo nối tiếp, đến hết dòng "(Tiếp theo Công báo số ...)"
                for i, l in enumerate(lines):
                    if l.startswith("(Tiếp theo"):
                        lines = lines[i + 1:]
                        break
            out += [(l, pno) for l in lines]
    return out


def parse(lines: list[tuple[str, int]]) -> list[Dieu]:
    dieus: list[Dieu] = []
    chuong = muc = ""
    cur: Dieu | None = None
    mode = None  # "chuong" | "muc" | "dieu_title" | "body"
    expected_dieu = 1
    for text, page in lines:
        if RE_END.search(text):
            break
        m_dieu = RE_DIEU.match(text)
        if m_dieu and int(m_dieu.group(1)) == expected_dieu:
            cur = Dieu(int(m_dieu.group(1)), m_dieu.group(2).strip(), page, chuong, muc)
            dieus.append(cur)
            expected_dieu += 1
            mode = "dieu_title"
            continue
        m_ch = RE_CHUONG.match(text)
        if m_ch and len(text) < 20:
            chuong, muc, mode = "Chương " + m_ch.group(1), "", "chuong"
            continue
        m_muc = RE_MUC.match(text)
        if m_muc and len(text) < 12:
            muc, mode = "Mục " + m_muc.group(1), "muc"
            continue
        if RE_PHAN.match(text) and len(text) < 30:
            mode = "chuong"
            continue
        if mode in ("chuong", "muc") and text.upper() == text:
            if mode == "chuong":
                chuong = (chuong + (". " if "." not in chuong else " ") + text).strip()
            else:
                muc = (muc + (". " if "." not in muc else " ") + text).strip()
            if cur is None or (cur.chuong != chuong):
                pass
            continue
        if cur is None:
            continue  # lời nói đầu, căn cứ ban hành
        if mode == "dieu_title" and not RE_KHOAN.match(text) and not RE_DIEM.match(text) and (
                text[:1].islower() or cur.tieu_de.endswith(",")
                or (len(text) <= 50 and not text.endswith((".", ":", ";")))):
            # Đề mục Điều bị xuống dòng. Dòng nối có thể viết hoa ("Việt Nam", "Nhà nước thu hồi đất"),
            # nhưng ngắn và không kết thúc câu; dòng đầu của nội dung thường dài cả dòng.
            cur.tieu_de += " " + text
            continue
        mode = "body"
        m_k = RE_KHOAN.match(text)
        if m_k and int(m_k.group(1)) == len(cur.khoan) + 1:
            cur.khoan.append({"so": int(m_k.group(1)), "dong": [text], "trang": page})
        elif cur.khoan:
            cur.khoan[-1]["dong"].append(text)
        else:
            cur.mo_dau.append(text)
    return dieus


RE_PAGE = re.compile(r"<<<trang ([\d_]+)>>>")
RE_DIEU_FLAT = re.compile(r"(?<![\wÀ-ỹ])Đi[eêềếểễệ]u\s*(\d{1,3})\s*[.,:;]\s*", re.I)
RE_NOI_NHAN = re.compile(r"Nơi\s*nhận\s*[:;]", re.I)
RE_CHUONG_FLAT = re.compile(r"(?<![\wÀ-ỹ])CH[ƯU]ƠNG\s+([IVXLC]+)\b", re.I)
UPPER_START = "A-ZĐÀÁẢÃẠÂẦẤẨẪẬĂẰẮẲẴẶÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
RE_KHOAN_FLAT = re.compile(r"(?<![\d/,.])(?<!khoản )(?<!Khoản )(?<!Điều )(?<!điểm )(?<!ngày )(?<!năm )(?<!tháng )"
                           r"(?<!số )(?<!Số )\b(\d{1,2})\s*[.,]?\s+(?=[%s])" % UPPER_START)


def parse_flat(text: str) -> list[Dieu]:
    """Tách văn bản OCR (đoạn bị gộp, mất xuống dòng) theo Chương/Điều/Khoản.

    Nhận "Điều N" theo đúng thứ tự tăng dần; khoản "N." cũng phải tăng dần trong từng Điều.
    Số đứng sau "khoản", "Điều", "điểm", "ngày", "năm", "tháng", "số" không được coi là khoản.
    """
    # Ghép các trang thành một chuỗi, nhớ vị trí bắt đầu của từng trang (gộp khoảng trắng trước khi ghép
    # để vị trí không bị lệch).
    parts = RE_PAGE.split(text)  # [trước trang đầu, mã trang, nội dung, mã trang, nội dung, ...]
    flat, offsets = "", []
    for pg, seg in zip(parts[1::2], parts[2::2]):
        offsets.append((len(flat), pg))
        flat += " " + re.sub(r"\s+", " ", seg).strip()

    def page_ref(i: int) -> str:
        p = "0_0"
        for off, pg in offsets:
            if off <= i:
                p = pg
            else:
                break
        return p

    def page_at(i: int) -> int:
        return int(page_ref(i).split("_")[-1])

    # OCR hay đọc số 1 trong số Điều thành chữ l/I ("Điều 1l1."): đổi lại (cùng độ dài, vị trí không lệch).
    flat = re.sub(r"(?<=Điều )(?=[\dlI]{2,3}\s*[.,:;])(?=\S*\d)[\dlI]{2,3}",
                  lambda m: m.group(0).replace("l", "1").replace("I", "1"), flat)
    chuongs = [(m.start(), "Chương " + m.group(1).upper()) for m in RE_CHUONG_FLAT.finditer(flat)]
    # Ứng viên đề mục: "Điều N." (hoặc ":") rồi đến chữ hoa; loại dẫn chiếu ("tại Điều 17.", "khoản 2 Điều 8,")
    # và Điều nằm trong ngoặc kép (nội dung được sửa đổi của văn bản khác: “Điều 10. ...”).
    cands = []
    for m in RE_DIEU_FLAT.finditer(flat):
        if not re.match(r"[%s]" % UPPER_START, flat[m.end():m.end() + 1]) or re.match(r"Điều\s*\d", flat[m.end():m.end() + 8]):
            continue
        # OCR hay đọc dấu chấm sau số Điều thành "," hoặc ";": chỉ nhận khi ngay trước là hết câu.
        if re.search(r"[,;]", m.group(0)) and not re.search(r"[.;:)]\s*$", flat[max(0, m.start() - 4):m.start()]):
            continue
        before = flat[max(0, m.start() - 14):m.start()].lower()
        if re.search(r"(tại|theo|của|và|các|khoản \d+|điểm \w|sau:?)\s*$", before) or \
                re.search(r"[\"'“”‘’<«]\s*\d*\s*$", flat[max(0, m.start() - 6):m.start()]):
            continue
        cands.append((m.start(), m.end(), int(m.group(1))))
    # Chọn dãy Điều tăng dần dài nhất, phạt mỗi số bị nhảy cóc (trang scan thiếu) để ưu tiên dãy liền mạch.
    GAP = 0.6
    score, prev = [], []
    for i, (_, _, n) in enumerate(cands):
        best, arg = (1 - GAP * (n - 1)) if n <= 11 else None, None
        for j in range(i):
            nj = cands[j][2]
            if nj < n <= nj + 11 and score[j] is not None:
                s = score[j] + 1 - GAP * (n - nj - 1)
                if best is None or s > best:
                    best, arg = s, j
        score.append(best)
        prev.append(arg)
    heads = []
    if any(s is not None for s in score):
        i = max((k for k in range(len(cands)) if score[k] is not None), key=lambda k: score[k])
        while i is not None:
            heads.append(cands[i])
            i = prev[i]
        heads.reverse()
    dieus = []
    for k, (s, e, n) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(flat)
        phu_luc, pl_start = "", 0
        if k + 1 == len(heads):
            # Điều cuối: phần sau "Nơi nhận:" là khối nơi nhận/chữ ký rồi phụ lục, mẫu biểu, không thuộc Điều.
            nn = RE_NOI_NHAN.search(flat, e)
            if nn:
                end, phu_luc, pl_start = nn.start(), flat[nn.start():].strip(), nn.start()
        body = flat[e:end]
        cut = next((c for c in reversed(chuongs) if c[0] < s), None)
        chuong = cut[1] if cut else ""
        # bỏ đề mục Chương/Mục dính ở cuối thân Điều trước
        nxt_ch = next((c for c in chuongs if s < c[0] < end), None)
        if nxt_ch:
            body = flat[e:nxt_ch[0]]
        khoan_pos, want = [], 1
        for km in RE_KHOAN_FLAT.finditer(body):
            if int(km.group(1)) == want:
                khoan_pos.append((km.start(), km.end(), want))
                want += 1
        if khoan_pos and khoan_pos[0][0] <= 300:
            title = body[:khoan_pos[0][0]].strip()
            mo_dau = []
        else:
            # Không có khoản: lấy đề mục đến hết câu đầu tiên hợp lý (tối đa 160 ký tự).
            m_t = re.match(r"(.{5,160}?)(?=\s[%s][a-zà-ỹ]+\s)" % UPPER_START, body)
            title = (m_t.group(1) if m_t else body[:120]).strip()
            mo_dau = [body[len(m_t.group(1)) if m_t else 120:].strip()]
            khoan_pos = []
        d = Dieu(n, title, page_at(s), chuong, "")
        d.mo_dau = mo_dau
        d.phu_luc, d.trang_phu_luc = phu_luc, page_at(pl_start) if phu_luc else 0
        d.tep = int(page_ref(s).split("_")[0])
        for j, (ks, ke, kn) in enumerate(khoan_pos):
            kend = khoan_pos[j + 1][0] if j + 1 < len(khoan_pos) else len(body)
            ktext = "%d. %s" % (kn, body[ke:kend].strip())
            ktext = re.sub(r"\s([a-zđ])\)\s", r"\n\1) ", ktext)
            d.khoan.append({"so": kn, "dong": ktext.split("\n"), "trang": page_at(e + ks)})
        dieus.append(d)
    return dieus


def join(lines: list[str]) -> str:
    """Ghép dòng bị xuống dòng thành đoạn; giữ xuống dòng trước điểm a), b)..."""
    out = []
    for l in lines:
        if out and not RE_DIEM.match(l):
            out[-1] += " " + l
        else:
            out.append(l)
    return "\n".join(re.sub(r"\s+", " ", x).strip() for x in out)


def split_long(text: str) -> list[str]:
    """Khoản quá dài thì tách theo nhóm điểm, mỗi phần lặp lại câu dẫn của khoản."""
    if len(text) <= MAX_CHUNK:
        return [text]
    parts = text.split("\n")
    head, points = parts[0], parts[1:]
    if len(head) > MAX_CHUNK // 2:
        # Câu dẫn quá dài (thường là OCR không nhận được điểm a, b): cắt theo câu.
        return split_sentences(text)
    groups, buf = [], []
    for p in points:
        if buf and len(head) + sum(len(x) for x in buf) + len(p) > MAX_CHUNK:
            groups.append(buf)
            buf = []
        buf.append(p)
    if buf:
        groups.append(buf)
    out = [head + "\n" + "\n".join(g) for g in groups] if groups else [text]
    # Một điểm đơn lẻ vẫn quá dài thì cắt tiếp theo câu.
    return [x for piece in out for x in (split_sentences(piece) if len(piece) > MAX_CHUNK else [piece])]


def split_sentences(text: str) -> list[str]:
    """Cắt theo ranh giới câu (hoặc dấu ;) thành các phần không quá MAX_CHUNK ký tự."""
    sents = re.split(r"(?<=[.;:])\s+(?=\S)", text)
    out, buf = [], ""
    for s in sents:
        while len(s) > MAX_CHUNK:  # câu không có dấu ngắt: cắt cứng ở khoảng trắng
            cut = s.rfind(" ", 0, MAX_CHUNK)
            cut = cut if cut > 0 else MAX_CHUNK
            if buf:
                out.append(buf)
                buf = ""
            out.append(s[:cut])
            s = s[cut:].lstrip()
        if buf and len(buf) + 1 + len(s) > MAX_CHUNK:
            out.append(buf)
            buf = s
        else:
            buf = (buf + " " + s) if buf else s
    if buf:
        out.append(buf)
    return out


OCR_DIR = ROOT / "data" / "ocr_sua"


def parse_ocr(row: dict) -> tuple[list[Dieu], str, list[str]]:
    """Tách bản OCR đã sửa dấu. Văn bản có nhiều file scan thì tách từng file, chọn file ra nhiều Điều nhất."""
    text = (OCR_DIR / (row["ma"] + ".txt")).read_text(encoding="utf-8")
    files = row["files"].split(";")
    best, best_file, notes = [], files[0], []
    for fi, f in enumerate(files, start=1):
        part = "\n".join(x for x in re.split(r"(?=<<<trang )", text) if x.startswith("<<<trang %d_" % fi))
        dieus = parse_flat(part)
        notes.append("%s: %d Điều" % (Path(f).name, len(dieus)))
        if len(dieus) > len(best):
            best, best_file = dieus, f
    if len(files) > 1:
        # Nhiều file có thể là các phần nối tiếp (BLDS: phần 1 Điều 1–365, phần 2 Điều 366–689):
        # ghép theo thứ tự, chỉ dùng bản ghép khi ra nhiều Điều hơn hẳn file tốt nhất.
        joined = parse_flat(text)
        if len(joined) > len(best):
            return joined, ";".join(files), ["ghép %d file nối tiếp (%s)" % (len(files), ", ".join(notes))]
        notes = ["chọn %s (%s)" % (Path(best_file).name, ", ".join(notes))]
    else:
        notes = []
    return best, best_file, notes


def build(row: dict, base: Path) -> tuple[list[dict], list[dict], list[str]]:
    files = row["files"].split(";")
    ma, ten, so_hieu = row["ma"], row["ten"], row["so_hieu"]
    issues = []
    if row["dinh_dang"] == "pdf_scan":
        dieus, src_file, issues = parse_ocr(row)
        files, nguon_text = [src_file], "ocr"
        part_files = src_file.split(";")
    else:
        dieus, nguon_text = parse(read_lines(base, files)), "pdf_text"
        part_files = files
    nam = re.search(r"/(\d{4})/", so_hieu).group(1)
    ten_ngan = "%s %s" % (ten, nam)
    dieu_rows, chunk_rows = [], []
    nums = [d.so for d in dieus]
    if nums != list(range(1, len(nums) + 1)):
        thieu = sorted(set(range(1, (nums[-1] if nums else 0) + 1)) - set(nums))
        issues.append("thiếu %d Điều%s" % (len(thieu), (": " + ", ".join(map(str, thieu[:15])) + ("…" if len(thieu) > 15 else "")) if thieu else ""))
    for d in dieus:
        vi_tri = " › ".join(x for x in (ten_ngan, d.chuong, d.muc, "Điều %d. %s" % (d.so, d.tieu_de)) if x)
        mo_dau = join(d.mo_dau)
        khoans = [{"so": k["so"], "text": join(k["dong"]), "trang": k["trang"]} for k in d.khoan]
        full = "\n".join(x for x in [mo_dau] + [k["text"] for k in khoans] if x)
        if not full:
            issues.append("Điều %d rỗng" % d.so)
        nguon = files[0] if len(files) == 1 else row["files"]
        if nguon_text == "ocr" and len(part_files) > 1:
            nguon = part_files[d.tep - 1]
        base_meta = {
            "van_ban": ma, "ten_van_ban": ten, "so_hieu": so_hieu, "chuong": d.chuong, "muc": d.muc,
            "dieu": d.so, "tieu_de_dieu": d.tieu_de, "ngay_hieu_luc": row["ngay_hieu_luc"],
            "nguon_file": nguon, "trang": d.trang,
            # "ocr": chữ có thể còn sai sau khi sửa dấu; khi trả lời chỉ dẫn chiếu, không trích nguyên văn.
            "nguon_text": nguon_text,
        }
        sua = [{"khoan": k, "boi": v[0], "noi_dung_moi": v[1]} for (m_, di, k), v in SUA_DOI.items() if m_ == ma and di == d.so]
        dieu_rows.append({**base_meta, "id": "%s-D%d" % (ma, d.so), "vi_tri": vi_tri,
                          "text": "Điều %d. %s\n%s" % (d.so, d.tieu_de, full), "so_khoan": len(khoans), "sua_doi": sua})
        units = [(0, mo_dau, d.trang)] if mo_dau else []
        units += [(k["so"], k["text"], k["trang"]) for k in khoans]
        if not units:
            units = [(0, "", d.trang)]
        for so_k, text, trang in units:
            sd = SUA_DOI.get((ma, d.so, so_k))
            for i, piece in enumerate(split_long(text)):
                cid = "%s-D%d-K%d%s" % (ma, d.so, so_k, "-%d" % (i + 1) if len(text) > MAX_CHUNK else "")
                header = vi_tri + (" › Khoản %d" % so_k if so_k else "")
                chunk_rows.append({**base_meta, "id": cid, "parent_id": "%s-D%d" % (ma, d.so), "khoan": so_k or None,
                                   "trang": trang, "vi_tri": header, "text": piece,
                                   "sua_doi": {"boi": sd[0], "noi_dung_moi": sd[1]} if sd else None})
    # Phụ lục (mẫu hợp đồng, mẫu đơn...) của bản OCR: chunk riêng, không gắn Điều nào.
    pl = next((d for d in dieus if d.phu_luc), None)
    if pl:
        meta = {"van_ban": ma, "ten_van_ban": ten, "so_hieu": so_hieu, "chuong": "", "muc": "", "dieu": None,
                "tieu_de_dieu": "", "ngay_hieu_luc": row["ngay_hieu_luc"], "nguon_file": files[0],
                "nguon_text": nguon_text, "khoan": None, "sua_doi": None}
        for i, piece in enumerate(split_sentences(pl.phu_luc), start=1):
            chunk_rows.append({**meta, "id": "%s-PL-%d" % (ma, i), "parent_id": "%s-PL" % ma,
                               "trang": pl.trang_phu_luc, "vi_tri": "%s › Phụ lục (sau phần Nơi nhận)" % ten_ngan,
                               "text": piece})
        issues.append("phụ lục %d chunk" % sum(1 for c in chunk_rows if c["dieu"] is None))
    return dieu_rows, chunk_rows, issues


def main(base_dir: str, out_dir: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    base, out = Path(base_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [r for r in csv.DictReader((ROOT / "schemas" / "luat_catalog.csv").open(encoding="utf-8"))
            if r["dinh_dang"] == "pdf_text"
            or (r["dinh_dang"] == "pdf_scan" and (OCR_DIR / (r["ma"] + ".txt")).exists())]
    all_dieu, all_chunks = [], []
    for row in rows:
        d, c, issues = build(row, base)
        all_dieu += d
        all_chunks += c
        no_khoan = sum(1 for x in d if x["so_khoan"] == 0)
        longest = max((len(x["text"]) for x in c), default=0)
        print("%-12s %3d Điều | %4d chunk | %3d Điều không chia khoản | chunk dài nhất %d ký tự%s"
              % (row["ma"], len(d), len(c), no_khoan, longest, (" | VẤN ĐỀ: " + "; ".join(issues)) if issues else ""))
    with (out / "dieu.jsonl").open("w", encoding="utf-8") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in all_dieu)
    with (out / "chunks.jsonl").open("w", encoding="utf-8") as f:
        f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in all_chunks)
    print("Đã ghi %d Điều, %d chunk vào %s" % (len(all_dieu), len(all_chunks), out))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
