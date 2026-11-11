"""Dựng bộ hồ sơ KH002 chuẩn từ file zip đã qua chuyên gia sửa.

Cách chạy:
    python scripts/build_kh002.py "KH002 (1).zip" data/hoso/KH002

Kết quả: thư mục phẳng theo giai đoạn (G1..G5, QL), mọi file mang mã
KH002-Gx-NNN, và manifest.json theo schema 1.0. Chỉ dùng thư viện chuẩn.
File zip gốc không bị thay đổi.
"""
import hashlib
import io
import json
import os
import re
import shutil
import sys
import unicodedata
import zipfile
from datetime import date

MA_HO_SO = "KH002"
SCHEMA_VERSION = "1.0"
PHIEN_BAN = 4

CASE = {
    "loai_nguoi_mua": "vo_chong_dong_so_huu",
    "loai_san_pham": "lien_ke",
    "ma_can": "CT2-04",
    "qua_moi_gioi": True,
    "vay_ngan_hang": True,
    "cham_thanh_toan": False,
    "uy_quyen": False,
}

# id (không có tiền tố KH002-) -> doc_type
DOC_TYPES = {
    "G1-001": "phieu_thong_tin_khach_hang",
    "G1-002": "phieu_thong_tin_can_cuoc",
    "G1-003": "giay_chung_nhan_rieng_cua_can",
    "G1-004": "phieu_thong_tin_bat_dong_san",
    "G1-005": "phieu_xac_nhan_can_khong_ban_trung",
    "G1-006": "phieu_tinh_gia_ban_va_tien_do_thanh_toan",
    "G1-007": "chinh_sach_uu_dai",
    "G1-008": "xac_nhan_giu_cho_thanh_cong",
    "G1-009": "phieu_dang_ky_nguyen_vong_mua",
    "G1-010": "thoa_thuan_giu_cho",
    "G1-011": "hop_dong_dat_coc",
    "G1-012": "phieu_thu_tien_dat_coc",
    "G1-013": "phieu_xac_nhan_nhan_du_tien_dat_coc",
    "G1-014": "phieu_trinh_phe_duyet_giao_dich_dat_coc",
    "G1-015": "bien_ban_ban_giao_ho_so",
    "G1-016": "checklist_giai_doan_1",
    "G1-017": "phieu_kiem_tra_ho_so_khach_hang",
    "G1-018": "chinh_sach_hoa_hong",
    "G1-019": "hop_dong_moi_gioi",
    "G1-020": "phieu_gioi_thieu_khach_hang",
    "G1-021": "phieu_xac_nhan_nguon_khach_hang",
    "G1-022": "phieu_dang_ky_nhu_cau_vay",
    "G1-023": "danh_gia_so_bo_kha_nang_vay",
    "G2-001": "bien_ban_dan_khach_xem_nha",
    "G2-002": "bien_ban_xac_nhan_giao_dich",
    "G2-003": "bien_ban_doi_soat_tien_dat_coc",
    "G2-004": "bang_gia_san_pham_duoc_phe_duyet",
    "G2-005": "chinh_sach_ban_hang_dai_ly",
    "G2-006": "giay_gioi_thieu_nhan_vien_moi_gioi",
    "G2-007": "ho_so_nguoi_moi_gioi",
    "G2-008": "hop_dong_phan_phoi",
    "G2-009": "phieu_tu_van_san_pham",
    "G2-010": "phu_luc_danh_sach_san_pham",
    "G2-011": "phieu_xac_nhan_nhan_tien",
    "G2-012": "xac_nhan_nguon_san_pham",
    "G2-013": "phieu_chuyen_ho_so_khach_hang",
    "G2-014": "bang_tien_do_thanh_toan_cho_ngan_hang",
    "G2-015": "cam_ket_giao_giay_chung_nhan_cho_ngan_hang",
    "G2-016": "de_nghi_doi_chieu_xac_nhan_thu_nhap",
    "G2-017": "hop_dong_the_chap_sau_cap_gcn",
    "G2-018": "thoa_thuan_ba_ben",
    "G2-019": "hop_dong_tin_dung",
    "G2-020": "don_de_nghi_vay_von",
    "G2-021": "de_nghi_xac_nhan_thong_tin_can",
    "G2-022": "phieu_ke_khai_thong_tin_cu_tru",
    "G2-023": "thoa_thuan_cung_dung_ten",
    "G2-024": "phieu_kiem_tra_ho_so_khach_hang",
    "G2-025": "to_trinh_phe_duyet_giao_dich",
    "G2-026": "du_thao_quyet_dinh_phe_duyet_ban_san_pham",
    "G2-027": "quyet_dinh_bo_nhiem",
    "G2-028": "quyet_dinh_phan_cap_tham_quyen_ky",
    "G2-029": "hop_dong_mua_ban",
    "G2-030": "phu_luc_thong_tin_san_pham",
    "G2-031": "phu_luc_gia_ban",
    "G2-032": "phu_luc_tien_do_thanh_toan",
    "G2-033": "phu_luc_ban_ve_va_dien_tich",
    "G2-034": "phieu_xac_nhan_thong_tin_san_pham",
    "G2-035": "phu_luc_trang_thiet_bi_vat_lieu",
    "G2-036": "phu_luc_quan_ly_bao_hanh",
    "G2-037": "bien_ban_giao_nhan_hop_dong",
    "G2-038": "checklist_kiem_tra_chu_ky_va_ho_so",
    "G2-039": "phieu_kiem_tra_hien_trang_nha_dat",
    "G2-040": "chinh_sach_uu_dai_chiet_khau",
    "G4-001": "bien_ban_ban_giao_san_vuon_cong_hang_rao",
    "G4-002": "bien_ban_doi_chieu_moc_gioi_ranh_gioi",
    "G4-003": "dang_ky_huong_dan_hoan_thien_noi_that",
    "G4-004": "cam_ket_quy_hoach_kien_truc",
    "G4-005": "bien_ban_nghiem_thu_ban_giao_nha",
    "G4-006": "phieu_xac_thuc_du_dieu_kien_ban_giao",
    "G4-007": "thong_bao_ban_giao_nha",
    "G4-008": "bien_ban_ban_giao_thiet_bi",
    "G4-009": "phieu_bao_hanh",
    "G5-001": "bien_ban_giao_nhan_giay_chung_nhan",
    "G5-002": "phieu_theo_doi_tiep_nhan_va_tra_ket_qua",
    "G5-003": "bang_thong_tin_nghia_vu_tai_chinh",
    "G5-004": "don_dang_ky_bien_dong_dat_dai",
    "QL-001": "huong_dan_doi_chieu_sua_ho_so",
    "QL-002": "phieu_thong_tin_hon_nhan_dong_so_huu",
    "QL-003": "phe_duyet_tin_dung_dieu_kien_giai_ngan",
    "QL-004": "bien_ban_giao_ban_goc_gcn_cho_ngan_hang",
    "QL-005": "theo_doi_chung_tu_thue_phi_le_phi",
}
# Giai đoạn 3: 5 loại chứng từ cho mỗi đợt 1..5, rồi 3 loại giải ngân cho đợt 2..5
G3_THANH_TOAN = [
    "bang_tinh_nghia_vu_thanh_toan",
    "doi_chieu_tien_ghi_co",
    "thong_tin_hoa_don_dien_tu",
    "thong_bao_thanh_toan",
    "xac_nhan_thanh_toan",
]
G3_GIAI_NGAN = ["khe_uoc_nhan_no", "xac_nhan_giai_ngan", "de_nghi_giai_ngan"]
G3_TRANCHE = {}
for _dot in range(1, 6):
    for _k, _t in enumerate(G3_THANH_TOAN):
        _id = "G3-%03d" % ((_dot - 1) * 5 + _k + 1)
        DOC_TYPES[_id] = _t
        G3_TRANCHE[_id] = _dot
for _dot in range(2, 6):
    for _k, _t in enumerate(G3_GIAI_NGAN):
        _id = "G3-%03d" % (26 + (_dot - 2) * 3 + _k)
        DOC_TYPES[_id] = _t
        G3_TRANCHE[_id] = _dot

# File trong zip chưa mang mã: (giai đoạn, tên file viết thường) -> id
UNCODED = {
    (1, "phieu_thong_tin_khach_hang.docx"): "G1-001",
    (1, "phieu_thong_tin_can_cuoc.docx"): "G1-002",
    (1, "giấy chứng nhận riêng của căn.docx"): "G1-003",
    (1, "phiếu thông tin bds.docx"): "G1-004",
    (1, "phiếu xác nhận căn không bị bán trùng.docx"): "G1-005",
    (1, "phiếu tính giá bán và tiến độ thanh toán.docx"): "G1-006",
    (1, "chính sách ưu đãi.docx"): "G1-007",
    (1, "xác nhận giữ chố thành công.docx"): "G1-008",
    (1, "phiếu đăng ký nguyện vọng mua bất động sản.docx"): "G1-009",
    (1, "thoả thuận giữ chỗ.docx"): "G1-010",
    (1, "hợp đồng đặt cọc.docx"): "G1-011",
    (1, "phiếu thu tiền đặt cọc.docx"): "G1-012",
    (1, "phiếu xác nhận đã nhận đủ tiền đặt cọc.docx"): "G1-013",
    (1, "phieu_trinh_phe_duyet_giao_dich_dat_coc.docx"): "G1-014",
    (1, "biên bản bàn giao.docx"): "G1-015",
    (1, "checklist.docx"): "G1-016",
    (1, "kiem_tra_ho_so_khach_hang.docx"): "G1-017",
    (1, "chính sách hoa hồng.docx"): "G1-018",
    (1, "hợp đồng mô giới.docx"): "G1-019",
    (1, "phieu_gioi_thieu_khach_hang.docx"): "G1-020",
    (1, "phieu_xac_nhan_nguon_khach_hang.docx"): "G1-021",
    (1, "dang_ky_nhu_cau_vay_mau.docx"): "G1-022",
    (1, "danh_gia_so_bo_kha_nang_vay.docx"): "G1-023",
    (2, "bien_ban_dan_khach_xem_nha.docx"): "G2-001",
    (2, "bien_ban_xac_nhan_giao_dich.docx"): "G2-002",
    (2, "bien_ban_doi_soat_tien_dat_coc.docx"): "G2-003",
    (2, "bang_gia_san_pham.docx"): "G2-004",
    (2, "chinh_sach_ban_hang_dai_ly.docx"): "G2-005",
    (2, "ho_so_nguoi_moi_gioi.docx"): "G2-007",
    (2, "hop_dong_phan_phoi.docx"): "G2-008",
    (2, "phieu_tu_van_san_pham.docx"): "G2-009",
    (2, "phu_luc_danh_sach_san_pham.docx"): "G2-010",
    (2, "phieu_xac_nhan_nhan_tien.docx"): "G2-011",
    (2, "xac_nhan_nguon_san_pham.docx"): "G2-012",
    (2, "phieu_chuyen_ho_so_khach_hang.docx"): "G2-013",
    (2, "phieu_kiem_tra_ho_so_khach_hang.docx"): "G2-024",
    (2, "trinh_phe_duyet_giao_dich.docx"): "G2-025",
    (2, "du_thao_quyet_dinh_phe_duyet_ban_san_pham.docx"): "G2-026",
    (2, "quyết định bổ nhiệm.docx"): "G2-027",
    (2, "quyết định phân cấp thẩm quyền ký.docx"): "G2-028",
    (2, "hop_dong_cap_nhat_tien_thanh_toan.docx"): "G2-029",
    (2, "phu_luc_thong_tin_san_pham.docx"): "G2-030",
    (2, "phu_luc_gia_ban.docx"): "G2-031",
    (2, "phu_luc_tien_do_thanh_toan.docx"): "G2-032",
    (2, "phu_luc_ban_ve_va_dien_tich.docx"): "G2-033",
    (2, "phieu_xac_nhan_thong_tin_san_pham.docx"): "G2-034",
    (2, "phu_luc_trang_thiet_bi_vat_lieu.docx"): "G2-035",
    (2, "bien_ban_giao_nhan_hop_dong.docx"): "G2-037",
    (2, "checklist_kiem_tra_chu_ky_va_ho_so.docx"): "G2-038",
    (2, "phiếu kiểm tra hiện trạng nhà, đất.docx"): "G2-039",
    (2, "chinh_sach_uu_dai_chiet_khau.docx"): "G2-040",
    (2, "bien_ban_xac_nhan_giao_dich_cap_nhat.docx"): "G2-002",
}

REQUIRED = {
    "Cốt lõi": "cot_loi",
    "Bổ sung": "bo_sung",
    "Cần theo trường hợp": "can_theo_truong_hop",
    "Quản lý": "quan_ly",
}
STATUS = {"Chờ xác nhận": "cho_xac_nhan"}


def nfc(s):
    return unicodedata.normalize("NFC", s)


def zip_name(info):
    """Tên file trong zip của macOS là UTF-8 dạng NFD nhưng không bật cờ UTF-8."""
    name = info.filename
    if not info.flag_bits & 0x800:
        try:
            name = name.encode("cp437").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return nfc(name)


def branch_of(doc_id):
    g, n = doc_id.split("-")
    n = int(n)
    if g == "G1":
        return "moi_gioi" if 18 <= n <= 21 else "vay_ngan_hang" if n >= 22 else "chung"
    if g == "G2":
        if n <= 13:
            return "moi_gioi"
        if n <= 21:
            return "vay_ngan_hang"
        if n <= 23:
            return "dong_so_huu"
        return "chung"
    if g == "G3":
        return "vay_ngan_hang" if n >= 26 else "chung"
    if g == "G4":
        return "nha_thap_tang" if n <= 4 else "chung"
    return "chung"


SKIP_TITLE = ("CỘNG HÒA", "CỘNG HOÀ", "ĐỘC LẬP", "ĐƠN VỊ", "CHỦ ĐẦU TƯ", "CÔNG TY", "ĐẠI LÝ",
              "NGÂN HÀNG", "TÊN CHỦ", "SỐ:", "DỰ THẢO", "THÔNG TIN KHÁCH HÀNG", "MẪU")


def docx_paragraphs(data):
    try:
        xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml").decode("utf-8")
    except Exception:
        return []
    out = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        text = re.sub(r"\s+", " ", "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", para))).strip()
        if text:
            out.append(text)
    return out


def docx_title(data):
    """Dòng tiêu đề của văn bản: dòng viết hoa đầu tiên, bỏ quốc hiệu và phần đầu trang."""
    paras = docx_paragraphs(data)
    for text in paras[:20]:
        letters = [c for c in text if c.isalpha()]
        if not 8 <= len(text) <= 120 or len(letters) < 6:
            continue
        if sum(c.isupper() for c in letters) / len(letters) < 0.8:
            continue
        if text.upper().startswith(SKIP_TITLE):
            continue
        return text
    for text in paras[:5]:
        if 8 <= len(text) <= 120 and not text.upper().startswith(SKIP_TITLE):
            return text
    return ""


def iso_date(s):
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", s or "")
    return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1)) if m else None


def main(zip_path, out_dir):
    z = zipfile.ZipFile(zip_path)
    entries = {}
    for info in z.infolist():
        name = zip_name(info)
        base = os.path.basename(name)
        if name.startswith("__MACOSX") or name.endswith("/"):
            continue
        if base.startswith("~$") or base == ".DS_Store":
            continue
        entries[name.split("/", 1)[1]] = info

    old = json.loads(z.read(entries["00_Quan_ly_ho_so/metadata_KH002.json"]))
    old_by_id = {d["id"].split("-", 1)[1]: d for d in old["tai_lieu"]}

    picked = {}      # id -> (đường dẫn trong zip, bytes)
    dropped = []     # file trùng bị loại
    unmapped = []    # file không xác định được mã
    assets = []
    for rel, info in sorted(entries.items()):
        base = os.path.basename(rel)
        data = z.read(info)
        if rel.endswith("metadata_KH002.json"):
            continue
        if not base.lower().endswith(".docx"):
            assets.append((rel, data))
            continue
        m = re.match(r"KH002-(G\d|QL)-(\d{3})_", base)
        if m:
            doc_id = "%s-%s" % (m.group(1), m.group(2))
        else:
            stage = int(re.match(r"Giai đoạn (\d)", rel).group(1))
            key = (stage, re.sub(r"\s+", " ", base.strip().lower()).replace(" .docx", ".docx"))
            doc_id = UNCODED.get(key)
            if doc_id is None and stage == 3 and "xác nhận giải ngân" in base:
                dot = int(re.search(r"Đợt (\d)", rel).group(1))
                doc_id = "G3-%03d" % (27 + (dot - 2) * 3)
        if doc_id is None:
            unmapped.append(rel)
            continue
        if doc_id in picked:
            # Hai file cùng mã: giữ bản được sửa sau cùng, ghi bản còn lại vào danh sách tồn đọng.
            prev_rel, prev_data, prev_time = picked[doc_id]
            keep_new = info.date_time > prev_time
            lose_rel, lose_data = (prev_rel, prev_data) if keep_new else (rel, data)
            win_data = data if keep_new else prev_data
            dropped.append({"zip_path": lose_rel, "trung_voi": "KH002-" + doc_id,
                            "van_ban_giong_het": docx_paragraphs(lose_data) == docx_paragraphs(win_data),
                            "ly_do": "giữ bản có thời điểm sửa muộn hơn trong zip"})
            if not keep_new:
                continue
        picked[doc_id] = (rel, data, info.date_time)

    if unmapped:
        sys.exit("Không gán được mã cho: %s" % unmapped)

    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    docs = []
    for doc_id in sorted(picked):
        rel, data, _ = picked[doc_id]
        folder = doc_id.split("-")[0]
        doc_type = DOC_TYPES[doc_id]
        tranche = G3_TRANCHE.get(doc_id)
        fname = "KH002-%s_%s%s.docx" % (doc_id, doc_type, "_dot_%d" % tranche if tranche else "")
        os.makedirs(os.path.join(out_dir, folder), exist_ok=True)
        with open(os.path.join(out_dir, folder, fname), "wb") as f:
            f.write(data)
        o = old_by_id.get(doc_id, {})
        ref = o
        docs.append({
            "id": "KH002-" + doc_id,
            "file": "%s/%s" % (folder, fname),
            "title": docx_title(data),
            "doc_type": doc_type,
            "stage": int(folder[1]) if folder != "QL" else o.get("stage", 0),
            "tranche": tranche,
            "branch": branch_of(doc_id),
            "date": iso_date(ref.get("date")),
            "issuer": ref.get("issuer"),
            "signers": [s.strip() for s in (ref.get("signers") or "").split(";") if s.strip()],
            "required": REQUIRED.get(ref.get("required"), None),
            "status": STATUS.get(ref.get("status"), "cho_xac_nhan"),
            "sha256": hashlib.sha256(data).hexdigest(),
            "zip_path": rel,
            "noi_dung_khop_metadata_v3": o.get("sha256") == hashlib.sha256(data).hexdigest() if o else None,
        })

    asset_rows = []
    for rel, data in assets:
        fname = os.path.basename(rel)
        os.makedirs(os.path.join(out_dir, "QL", "ban_ve"), exist_ok=True)
        with open(os.path.join(out_dir, "QL", "ban_ve", fname), "wb") as f:
            f.write(data)
        asset_rows.append({"file": "QL/ban_ve/" + fname, "sha256": hashlib.sha256(data).hexdigest(), "zip_path": rel})

    missing = sorted(set(old_by_id) - set(picked))
    issues = []
    for doc_id in missing:
        issues.append({"loai": "thieu_tai_lieu", "id": "KH002-" + doc_id,
                       "mo_ta": "Có trong metadata phiên bản 3 (%s) nhưng không có file trong zip."
                                % os.path.basename(old_by_id[doc_id]["file"])})
    for d in dropped:
        issues.append({"loai": "file_trung_da_loai", **d})
    issues.append({"loai": "thieu_workbook", "mo_ta": "Hướng dẫn KH002-QL-001 nhắc workbook Checklist_KH002.xlsx "
                   "nhưng trong zip chỉ có file khóa tạm ~$Checklist_KH002.xlsx."})

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "ma_ho_so": MA_HO_SO,
        "phien_ban": PHIEN_BAN,
        "ngay_dung": date.today().isoformat(),
        "nguon": {"zip": os.path.basename(zip_path), "metadata_goc_phien_ban": old.get("phien_ban"),
                  "ngay_ra_soat_goc": iso_date(old.get("ngay_ra_soat"))},
        "loai_du_lieu": old.get("loai_du_lieu"),
        "document_provenance": old.get("document_provenance"),
        "case": CASE,
        "tai_lieu": docs,
        "tep_dinh_kem": asset_rows,
        "van_de_ton_dong": issues,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    changed = sum(1 for d in docs if d["noi_dung_khop_metadata_v3"] is False)
    print("Tài liệu: %d | tệp đính kèm: %d | nội dung khác metadata v3: %d | vấn đề tồn đọng: %d"
          % (len(docs), len(asset_rows), changed, len(issues)))
    for i in issues:
        print(" -", i["loai"], i.get("id", ""), i.get("zip_path", ""), i.get("van_ban_giong_het", ""))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
