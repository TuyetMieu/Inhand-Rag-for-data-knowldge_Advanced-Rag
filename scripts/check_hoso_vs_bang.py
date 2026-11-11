"""Đối chiếu số liệu một bộ hồ sơ (docx) với bảng dữ liệu trong SQLite.

Với mỗi giá trị trong SQLite (giá, diện tích, cọc, các đợt, ngày, CCCD...), đếm số văn bản
trong hồ sơ có chứa giá trị đó. Giá trị không xuất hiện ở văn bản nào là dấu hiệu lệch.

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python scripts/check_hoso_vs_bang.py data/hoso/KH002 data/bang/bang.sqlite3
"""
import json
import re
import sqlite3
import sys
import zipfile
from pathlib import Path


def docx_text(path: Path) -> str:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"</w:p>", "\n", xml)))


def variants(col: str, value) -> list[str]:
    """Các cách viết một giá trị thường gặp trong văn bản tiếng Việt."""
    if value is None:
        return []
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int):
        return [f"{value:,}".replace(",", "."), str(value)]
    if isinstance(value, float):
        s = ("%g" % value)
        return [s.replace(".", ","), s]
    s = str(value)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        y, mo, d = m.groups()
        return ["%s/%s/%s" % (d, mo, y), "%d/%d/%s" % (int(d), int(mo), y)]
    return [s]


CHECKS = {
    "mua_ban": ["ma_can", "phan_khu", "dt_dat_m2", "dtxd_m2", "gia_truoc_vat", "vat", "kpbt", "gia_gom_vat_kpbt"],
    "giao_dich": ["ngay_giu_cho", "so_phieu_giu_cho", "tien_giu_cho", "ngay_dat_coc", "so_hd_dat_coc",
                  "tien_dat_coc", "ngay_ky_hdmb", "so_hdmb", "gia_tri_hdmb", "dai_ly", "moi_gioi",
                  "ngan_hang", "so_tien_vay"],
    "tien_do_thanh_toan": ["dot_1", "dot_2", "dot_3", "dot_4_ban_giao", "dot_5_nhan_gcn"],
    "ban_giao": ["ngay_du_kien_ban_giao", "ngay_ban_giao", "so_hs_dang_ky_bien_dong", "ngay_nop_hs_sang_ten",
                 "so_gcn_moi", "ngay_nhan_gcn"],
    "khach_hang": ["ho_ten", "ngay_sinh", "cccd", "ngay_cap_cccd", "sdt", "email", "vo_chong_ho_ten",
                   "vo_chong_cccd", "so_dkkh"],
}


def main(hoso_dir: str, db: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(hoso_dir)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    ma = manifest["ma_ho_so"]
    texts = {d["id"]: docx_text(root / d["file"]) for d in manifest["tai_lieu"] if d["file"].endswith(".docx")}
    con = sqlite3.connect(db)
    lech = 0
    for table, cols in CHECKS.items():
        cur = con.execute("SELECT %s FROM %s WHERE ma_kh = ?" % (", ".join(cols), table), (ma,))
        row = cur.fetchone()
        if row is None:
            print("%s: không có %s" % (table, ma))
            continue
        for col, value in zip(cols, row):
            vs = variants(col, value)
            if not vs:
                continue
            hits = [i for i, t in texts.items() if any(v in t for v in vs)]
            flag = "OK " if hits else "LỆCH"
            lech += not hits
            print("%s %s.%s = %s | có trong %d văn bản%s" % (
                flag, table, col, value, len(hits), (" (" + ", ".join(hits[:3]) + ("…" if len(hits) > 3 else "") + ")") if hits else ""))
    print("\nKẾT QUẢ: %d giá trị không tìm thấy trong hồ sơ %s" % (lech, ma))
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
