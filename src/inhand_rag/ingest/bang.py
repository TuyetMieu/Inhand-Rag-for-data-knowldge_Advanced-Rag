"""Nạp file Excel dữ liệu mẫu (6 sheet) vào SQLite và kiểm chất lượng dữ liệu.

Cách chạy (từ gốc repo):
    .venv\\Scripts\\python -m inhand_rag.ingest.bang "..\\Data\\Du_lieu_mau_100_final.xlsx" data\\bang\\bang.sqlite3

Mỗi sheet thành một bảng với tên cột không dấu. Tiền là số nguyên (đồng), ngày theo ISO.
Báo cáo kiểm tra in ra màn hình; không sửa dữ liệu nguồn.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd

# sheet -> (tên bảng, dòng tiêu đề (0 = dòng 1), {tên cột gốc: tên cột mới})
SHEETS = {
    "Bang_gia_100_can": ("bang_gia", 0, {
        "Tình trạng": "tinh_trang", "STT": "stt", "Phân khu": "phan_khu", "Mã căn": "ma_can",
        "Loại Hình": "loai_hinh", "Loại căn": "loai_can", "TCBG": "tieu_chuan_ban_giao",
        "DT đất\n(m²)": "dt_dat_m2", "DTXD\n(m²)": "dtxd_m2", "Giá bán trước\nVAT": "gia_truoc_vat",
        "VAT": "vat", "KPBT": "kpbt", "Giá bán gồm\nVAT và KPBT": "gia_gom_vat_kpbt",
        "Giá TTS": "gia_tts", "Đơn giá\nTTS/m²": "don_gia_tts_m2",
    }),
    "TT_Khách": ("khach_hang", 2, {
        "Mã KH": "ma_kh", "Họ và tên": "ho_ten", "Giới tính": "gioi_tinh", "Ngày sinh": "ngay_sinh",
        "CCCD": "cccd", "Ngày cấp CCCD": "ngay_cap_cccd", "Nơi cấp CCCD": "noi_cap_cccd",
        "Địa chỉ thường trú": "dia_chi", "SĐT": "sdt", "Email": "email",
        "Tình trạng hôn nhân": "hon_nhan", "Họ tên vợ/chồng": "vo_chong_ho_ten",
        "CCCD vợ/chồng": "vo_chong_cccd", "Số ĐKKH": "so_dkkh", "Ngày ĐKKH": "ngay_dkkh",
        "Có ủy quyền?": "uy_quyen", "Người được ủy quyền": "nguoi_duoc_uy_quyen",
        "CCCD người được ủy quyền": "cccd_nguoi_duoc_uy_quyen", "Số văn bản ủy quyền": "so_vb_uy_quyen",
    }),
    "TT_Mua": ("mua_ban", 2, {
        "Mã KH": "ma_kh", "Họ và tên": "ho_ten", "Dự án": "du_an", "Chủ đầu tư": "chu_dau_tu",
        "Quy mô dự án": "quy_mo_du_an", "Mật độ xây dựng": "mat_do_xay_dung", "Phân khu": "phan_khu",
        "Trục đường": "truc_duong", "STT căn": "stt_can", "Mã căn": "ma_can", "Loại hình": "loai_hinh",
        "Loại căn": "loai_can", "TCBG": "tieu_chuan_ban_giao", "DT đất (m²)": "dt_dat_m2",
        "DTXD (m²)": "dtxd_m2", "Tình trạng sản phẩm": "tinh_trang", "Giá bán trước VAT": "gia_truoc_vat",
        "VAT": "vat", "KPBT": "kpbt", "Giá bán gồm VAT và KPBT": "gia_gom_vat_kpbt",
        "Giá TTS": "gia_tts", "Đơn giá TTS/m²": "don_gia_tts_m2",
    }),
    "Bàn giao": ("ban_giao", 2, {
        "Mã KH": "ma_kh", "Họ và tên": "ho_ten", "Ngày dự kiến bàn giao": "ngay_du_kien_ban_giao",
        "Ngày bàn giao": "ngay_ban_giao", "Số hồ sơ đăng ký biến động": "so_hs_dang_ky_bien_dong",
        "Ngày nộp hồ sơ sang tên": "ngay_nop_hs_sang_ten", "Số GCN mới": "so_gcn_moi",
        "Ngày nhận GCN": "ngay_nhan_gcn", "Trạng thái hồ sơ": "trang_thai",
    }),
    "TĐ_Thanh toán": ("tien_do_thanh_toan", 2, {
        "Mã KH": "ma_kh", "Họ và tên": "ho_ten", "Đợt 1 - 20%": "dot_1", "Đợt 2 - 30%": "dot_2",
        "Đợt 3 - 30%": "dot_3", "Bàn giao - 10%": "dot_4_ban_giao", "Nhận GCN - 10%": "dot_5_nhan_gcn",
    }),
    "TK_Giao dịch": ("giao_dich", 2, {
        "Mã KH": "ma_kh", "Họ và tên": "ho_ten", "Ngày giữ chỗ": "ngay_giu_cho",
        "Số phiếu giữ chỗ": "so_phieu_giu_cho", "Tiền giữ chỗ": "tien_giu_cho", "Ngày đặt cọc": "ngay_dat_coc",
        "Số HĐ đặt cọc": "so_hd_dat_coc", "Tiền đặt cọc": "tien_dat_coc", "Ngày ký HĐMB": "ngay_ky_hdmb",
        "Số HĐMB": "so_hdmb", "Giá trị HĐMB": "gia_tri_hdmb", "Qua môi giới?": "qua_moi_gioi",
        "Đại lý": "dai_ly", "Môi giới": "moi_gioi", "Vay ngân hàng?": "vay_ngan_hang",
        "Ngân hàng": "ngan_hang", "Tỷ lệ vay": "ty_le_vay", "Số tiền vay": "so_tien_vay",
    }),
}

MONEY = {"gia_truoc_vat", "vat", "kpbt", "gia_gom_vat_kpbt", "gia_tts", "don_gia_tts_m2", "dot_1", "dot_2",
         "dot_3", "dot_4_ban_giao", "dot_5_nhan_gcn", "tien_giu_cho", "tien_dat_coc", "gia_tri_hdmb", "so_tien_vay"}
TEXT_ID = {"cccd", "vo_chong_cccd", "cccd_nguoi_duoc_uy_quyen", "sdt"}


def load_sheet(path: Path, sheet: str, header: int, columns: dict) -> tuple[pd.DataFrame, list[str]]:
    df = pd.read_excel(path, sheet_name=sheet, header=header, dtype=object)
    df.columns = [str(c).strip() if not str(c).startswith("Unnamed") else None for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c]]
    unknown = [c for c in df.columns if c not in columns and c.strip() not in columns]
    df = df.rename(columns={c: columns.get(c, columns.get(c.strip(), c)) for c in df.columns})
    key = "ma_kh" if "ma_kh" in df.columns else "ma_can"
    df = df[df[key].notna() & (df[key].astype(str).str.strip() != "")].copy()
    for col in df.columns:
        if col in MONEY:
            df[col] = pd.to_numeric(df[col], errors="coerce").round().astype("Int64")
        elif col.startswith("ngay"):
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
        elif col in TEXT_ID:
            df[col] = df[col].map(lambda v: None if pd.isna(v) else str(v).strip().split(".")[0])
        elif df[col].dtype == object:
            df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
    if "stt" in df.columns:
        df["stt"] = pd.to_numeric(df["stt"], errors="coerce").astype("Int64")
    return df, unknown


def quality_report(t: dict[str, pd.DataFrame]) -> list[str]:
    """Kiểm khóa nối và các ràng buộc số học giữa các bảng. Trả về danh sách vấn đề."""
    issues = []
    kh = set(t["khach_hang"]["ma_kh"])
    for name in ("mua_ban", "ban_giao", "tien_do_thanh_toan", "giao_dich"):
        ids = t[name]["ma_kh"]
        if ids.duplicated().any():
            issues.append("%s: trùng mã KH %s" % (name, sorted(ids[ids.duplicated()])))
        missing = sorted(set(ids) - kh)
        if missing:
            issues.append("%s: mã KH không có trong khach_hang: %s" % (name, missing))
        if set(kh) - set(ids):
            issues.append("%s: thiếu mã KH %s" % (name, sorted(kh - set(ids))))

    gia = t["bang_gia"].set_index("ma_can")
    mb = t["mua_ban"].set_index("ma_kh")
    for ma_can, nhom in t["mua_ban"].groupby("ma_can"):
        if len(nhom) > 1:
            issues.append("Căn %s bán trùng cho %d khách: %s" % (ma_can, len(nhom), ", ".join(sorted(nhom["ma_kh"]))))
    du_an = sorted(t["mua_ban"]["du_an"].dropna().unique())
    if len(du_an) > 1:
        issues.append("Tên dự án không thống nhất: %s" % du_an)
    for ma_kh, r in mb.iterrows():
        if r["ma_can"] not in gia.index:
            issues.append("%s: căn %s không có trong bang_gia" % (ma_kh, r["ma_can"]))
            continue
        g = gia.loc[r["ma_can"]]
        for col in ("gia_gom_vat_kpbt", "dt_dat_m2", "dtxd_m2"):
            a, b = r.get(col), g.get(col)
            if pd.notna(a) and pd.notna(b) and str(a) != str(b) and abs(float(a) - float(b)) > 0.01:
                issues.append("%s: %s lệch bang_gia (%s ≠ %s)" % (ma_kh, col, a, b))

    gd = t["giao_dich"].set_index("ma_kh")
    td = t["tien_do_thanh_toan"].set_index("ma_kh")
    dots = ["dot_1", "dot_2", "dot_3", "dot_4_ban_giao", "dot_5_nhan_gcn"]
    for ma_kh, r in gd.iterrows():
        hd = r["gia_tri_hdmb"]
        if ma_kh in mb.index and pd.notna(hd) and hd != mb.loc[ma_kh, "gia_gom_vat_kpbt"]:
            issues.append("%s: giá trị HĐMB %s ≠ giá trong mua_ban %s" % (ma_kh, hd, mb.loc[ma_kh, "gia_gom_vat_kpbt"]))
        if ma_kh in td.index and pd.notna(hd):
            tong = sum(int(td.loc[ma_kh, d]) for d in dots if pd.notna(td.loc[ma_kh, d]))
            if abs(tong - hd) > 5:
                issues.append("%s: tổng 5 đợt %s ≠ giá trị HĐMB %s (lệch %s)" % (ma_kh, tong, hd, tong - hd))
        if r.get("vay_ngan_hang") == "Có" and pd.notna(r.get("so_tien_vay")) and pd.notna(hd):
            ty_le = float(r["ty_le_vay"] or 0)
            if abs(r["so_tien_vay"] - round(hd * ty_le)) > 5:
                issues.append("%s: số tiền vay %s ≠ %.0f%% × HĐMB" % (ma_kh, r["so_tien_vay"], ty_le * 100))

    for _, r in t["khach_hang"].iterrows():
        for col in ("cccd", "vo_chong_cccd"):
            v = r.get(col)
            if isinstance(v, str) and v and v != "Không" and not (v.isdigit() and len(v) == 12):
                issues.append("%s: %s '%s' không đủ 12 chữ số" % (r["ma_kh"], col, v))
    return issues


def main(xlsx: str, out: str) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    tables, unknown_cols = {}, []
    for sheet, (name, header, cols) in SHEETS.items():
        df, unknown = load_sheet(Path(xlsx), sheet, header, cols)
        tables[name] = df
        unknown_cols += ["%s.%s" % (sheet, c) for c in unknown]
        print("%-20s %3d dòng, %2d cột" % (name, len(df), len(df.columns)))
    if unknown_cols:
        print("CẢNH BÁO: cột chưa đặt tên mới:", unknown_cols)

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()
    with sqlite3.connect(out_path) as con:
        for name, df in tables.items():
            df.to_sql(name, con, index=False)
        con.execute("CREATE UNIQUE INDEX ix_bang_gia ON bang_gia(ma_can)")
        for name in ("khach_hang", "mua_ban", "ban_giao", "tien_do_thanh_toan", "giao_dich"):
            con.execute("CREATE INDEX ix_%s ON %s(ma_kh)" % (name, name))
    print("Đã ghi", out_path)

    issues = quality_report(tables)
    print("\nKIỂM TRA CHẤT LƯỢNG: %d vấn đề" % len(issues))
    for i in issues:
        print(" -", i)
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
