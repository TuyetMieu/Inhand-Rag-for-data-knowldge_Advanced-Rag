"""Kiểm schemas/legal_rules.yaml và eval/golden.jsonl với dữ liệu thật của một hồ sơ.

1. Cấu trúc: id duy nhất, đủ trường, giá trị thuộc danh mục.
2. Tham chiếu: doc_type, mã tài liệu, quy tắc được nhắc tới đều tồn tại.
3. Kết quả mong đợi (`kh002`) đúng với dữ liệu:
   - nguong_ty_le, thoi_han: tính lại từ SQLite;
   - dieu_khoan_bat_buoc: dò mẫu `tim_trong_van_ban` trong các văn bản áp dụng;
   - theo_case có `dau_hieu_chua_dat`: dò dấu hiệu trong văn bản.

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/validate_rules.py data/hoso/KH002 data/bang/bang.sqlite3
"""
import json
import re
import sqlite3
import sys
import zipfile
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOAI = {"nguong_ty_le", "thoi_han", "dieu_khoan_bat_buoc", "theo_case", "nhat_quan_du_lieu"}
MUC_DO = {"vi_pham", "canh_bao", "can_bo_sung"}
NGUON = {"luat", "chuyen_gia", "doi_soat_du_lieu"}
TRANG_THAI = {"da_doi_chieu_pdf", "chua_co_trong_dataset", "nghiep_vu"}
KET_QUA = {"dat", "vi_pham", "thieu", "lech", "chua_xac_dinh"}
LOAI_CAU_HOI = {"ho_so", "so_lieu", "checklist", "phap_ly"}


def docx_text(path: Path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    paras = ["".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)) for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)]
    return re.sub(r"[ \t]+", " ", "\n".join(paras))


def main(hoso: str, db: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    errors, notes = [], []
    rules_doc = yaml.safe_load((ROOT / "schemas" / "legal_rules.yaml").read_text(encoding="utf-8"))
    golden = [json.loads(l) for l in (ROOT / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    manifest = json.loads((Path(hoso) / "manifest.json").read_text(encoding="utf-8"))
    ma = manifest["ma_ho_so"]
    docs = {d["id"]: d for d in manifest["tai_lieu"]}
    doc_types = {d["doc_type"] for d in docs.values()}
    texts_by_type = {}
    for d in docs.values():
        texts_by_type.setdefault(d["doc_type"], []).append((d["id"], docx_text(Path(hoso) / d["file"])))
    van_ban = rules_doc.get("van_ban", {})
    rules = rules_doc["quy_tac"]

    # 1-2. Cấu trúc và tham chiếu của quy tắc
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        errors.append("Trùng id quy tắc")
    for r in rules:
        rid = r["id"]
        for f in ("ten", "loai", "ap_dung", "can_cu", "nguon", "muc_do", "kh002"):
            if f not in r:
                errors.append("%s: thiếu trường %s" % (rid, f))
        if r.get("loai") not in LOAI:
            errors.append("%s: loai không hợp lệ" % rid)
        if r.get("muc_do") not in MUC_DO:
            errors.append("%s: muc_do không hợp lệ" % rid)
        if r.get("nguon") not in NGUON:
            errors.append("%s: nguon không hợp lệ" % rid)
        if r.get("nguon") == "chuyen_gia" and not r.get("nhan_xet_chuyen_gia"):
            errors.append("%s: nguồn chuyên gia nhưng thiếu nhan_xet_chuyen_gia" % rid)
        for c in r.get("can_cu", []):
            if c.get("trang_thai") not in TRANG_THAI:
                errors.append("%s: trạng thái căn cứ không hợp lệ" % rid)
            if c.get("van_ban") and c["van_ban"] not in van_ban:
                errors.append("%s: văn bản %s chưa khai báo" % (rid, c["van_ban"]))
            if c.get("trang_thai") == "da_doi_chieu_pdf" and not (c.get("van_ban") and c.get("dieu")):
                errors.append("%s: căn cứ đã đối chiếu PDF nhưng thiếu văn bản/điều" % rid)
        for dt in r.get("ap_dung", {}).get("doc_types", []):
            if dt != "*" and dt not in doc_types:
                errors.append("%s: doc_type %s không có trong %s" % (rid, dt, ma))
        if r.get("kh002", {}).get("ket_qua") not in KET_QUA:
            errors.append("%s: kh002.ket_qua không hợp lệ" % rid)
    for item in rules_doc.get("checklist_bo_sung", []):
        if item["quy_tac"] not in ids:
            errors.append("checklist_bo_sung %s: quy tắc %s không tồn tại" % (item["tai_lieu"], item["quy_tac"]))

    # 3. Kết quả mong đợi so với dữ liệu thật
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    row = {}
    for table in ("giao_dich", "tien_do_thanh_toan", "ban_giao"):
        r_ = con.execute("SELECT * FROM %s WHERE ma_kh = ?" % table, (ma,)).fetchone()
        row.update(dict(r_) if r_ else {})
    for r in rules:
        rid, loai, exp = r["id"], r["loai"], r["kh002"]
        tham_so = r.get("tham_so", {})
        if loai == "nguong_ty_le":
            tu = tham_so["tu_so"]
            tu_so = sum(row[c] for c in tu) if isinstance(tu, list) else row[tu]
            ty_le = tu_so / row[tham_so["mau_so"]]
            got = "dat" if ty_le <= tham_so["toi_da"] + 1e-9 else "vi_pham"
            notes.append("%s: %.4f so với tối đa %.2f -> %s" % (rid, ty_le, tham_so["toi_da"], got))
            if got != exp["ket_qua"] or abs(ty_le - exp.get("gia_tri", ty_le)) > 0.005:
                errors.append("%s: mong đợi %s (%s), tính được %s (%.4f)" % (rid, exp["ket_qua"], exp.get("gia_tri"), got, ty_le))
        elif loai == "thoi_han":
            so_ngay = (date.fromisoformat(row[tham_so["den_ngay"]]) - date.fromisoformat(row[tham_so["tu_ngay"]])).days
            got = "dat" if so_ngay <= tham_so["toi_da_ngay"] else "vi_pham"
            notes.append("%s: %d ngày so với tối đa %d -> %s" % (rid, so_ngay, tham_so["toi_da_ngay"], got))
            if got != exp["ket_qua"] or so_ngay != exp.get("gia_tri", so_ngay):
                errors.append("%s: mong đợi %s (%s), tính được %s (%d ngày)" % (rid, exp["ket_qua"], exp.get("gia_tri"), got, so_ngay))
        elif loai == "dieu_khoan_bat_buoc":
            rx = re.compile(tham_so["tim_trong_van_ban"], re.I)
            hits = [i for dt in r["ap_dung"]["doc_types"] for i, t in texts_by_type.get(dt, []) if rx.search(t)]
            got = "dat" if hits else "thieu"
            notes.append("%s: điều khoản %s%s" % (rid, "có ở " + ", ".join(hits) if hits else "không tìm thấy", ""))
            if got != exp["ket_qua"]:
                errors.append("%s: mong đợi %s, dò được %s %s" % (rid, exp["ket_qua"], got, hits))
        elif loai == "theo_case" and tham_so.get("dau_hieu_chua_dat"):
            hits = [(i, s) for dt in r["ap_dung"]["doc_types"] for i, t in texts_by_type.get(dt, [])
                    for s in tham_so["dau_hieu_chua_dat"] if s.lower() in t.lower()]
            got = "thieu" if hits else "dat"
            notes.append("%s: dấu hiệu chưa đạt %s" % (rid, hits or "không thấy"))
            if got != exp["ket_qua"]:
                errors.append("%s: mong đợi %s, dò được %s" % (rid, exp["ket_qua"], got))

    # Câu hỏi vàng
    gids = [g["id"] for g in golden]
    if len(gids) != len(set(gids)):
        errors.append("Trùng id câu hỏi vàng")
    for g in golden:
        if g.get("loai") not in LOAI_CAU_HOI:
            errors.append("%s: loai không hợp lệ" % g["id"])
        if not g.get("y_chinh"):
            errors.append("%s: thiếu ý chính" % g["id"])
        for q in g.get("quy_tac", []):
            if q not in ids:
                errors.append("%s: quy tắc %s không tồn tại" % (g["id"], q))
        for n in g.get("nguon", []):
            if n.startswith(ma + "-") and n not in docs:
                errors.append("%s: tài liệu %s không có trong manifest" % (g["id"], n))
            elif not n.startswith(ma + "-") and n.split()[0] not in van_ban:
                errors.append("%s: nguồn luật %s chưa khai báo" % (g["id"], n))

    print("Quy tắc: %d | câu hỏi vàng: %d | hồ sơ: %s" % (len(rules), len(golden), ma))
    for n in notes:
        print("  " + n)
    for e in errors:
        print("LỖI:", e)
    print("KẾT QUẢ: %s (%d lỗi)" % ("ĐẠT" if not errors else "KHÔNG ĐẠT", len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
