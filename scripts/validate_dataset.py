"""Kiểm tra một bộ hồ sơ theo schema manifest 1.0.

Cách chạy:
    python scripts/validate_dataset.py data/hoso/KH002

Thoát với mã 0 khi đạt mọi điều kiện, mã 1 khi có lỗi. Chỉ dùng thư viện chuẩn.
"""
import hashlib
import json
import os
import re
import sys
import zipfile

MAX_PATH = 200
REQUIRED_VALUES = {"cot_loi", "bo_sung", "can_theo_truong_hop", "quan_ly"}
BRANCH_VALUES = {"chung", "moi_gioi", "vay_ngan_hang", "dong_so_huu", "nha_thap_tang"}
DOC_FIELDS = ["id", "file", "title", "doc_type", "stage", "tranche", "branch", "date",
              "issuer", "signers", "required", "status", "sha256"]
CASE_FIELDS = ["loai_nguoi_mua", "loai_san_pham", "ma_can", "qua_moi_gioi",
               "vay_ngan_hang", "cham_thanh_toan", "uy_quyen"]


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def validate(root):
    errors, warnings = [], []
    mpath = os.path.join(root, "manifest.json")
    if not os.path.isfile(mpath):
        return ["Không có manifest.json"], warnings
    m = json.load(open(mpath, encoding="utf-8"))
    ma = m.get("ma_ho_so", "")

    if m.get("schema_version") != "1.0":
        errors.append("schema_version phải là 1.0")
    for f in CASE_FIELDS:
        if f not in m.get("case", {}):
            errors.append("case thiếu trường %s" % f)

    listed, ids = set(), set()
    for d in m.get("tai_lieu", []):
        did = d.get("id", "?")
        for f in DOC_FIELDS:
            if f not in d:
                errors.append("%s: thiếu trường %s" % (did, f))
        if did in ids:
            errors.append("%s: id trùng" % did)
        ids.add(did)
        if not re.fullmatch(re.escape(ma) + r"-(G[1-5]|QL)-\d{3}", did):
            errors.append("%s: id sai định dạng" % did)
        rel = d.get("file", "")
        listed.add(rel)
        full = os.path.join(root, rel)
        if not os.path.isfile(full):
            errors.append("%s: không có file %s" % (did, rel))
            continue
        if sha256(full) != d.get("sha256"):
            errors.append("%s: sha256 không khớp" % did)
        base = os.path.basename(rel)
        if not base.startswith(did + "_"):
            errors.append("%s: tên file không bắt đầu bằng id" % did)
        if not re.fullmatch(r"[A-Za-z0-9_\-/.]+", rel):
            errors.append("%s: đường dẫn có ký tự ngoài ASCII" % did)
        if len(os.path.abspath(full)) > MAX_PATH:
            errors.append("%s: đường dẫn dài hơn %d ký tự" % (did, MAX_PATH))
        if not re.fullmatch(r"[a-z0-9_]+", d.get("doc_type") or ""):
            errors.append("%s: doc_type sai định dạng" % did)
        elif d["doc_type"] not in base:
            errors.append("%s: tên file không chứa doc_type" % did)
        if d.get("date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["date"]):
            errors.append("%s: date không theo ISO" % did)
        if not isinstance(d.get("signers"), list):
            errors.append("%s: signers phải là mảng" % did)
        if d.get("branch") not in BRANCH_VALUES:
            errors.append("%s: branch không hợp lệ" % did)
        if d.get("required") not in REQUIRED_VALUES:
            errors.append("%s: required không hợp lệ" % did)
        if rel.lower().endswith(".docx"):
            try:
                xml = zipfile.ZipFile(full).read("word/document.xml").decode("utf-8")
                if len(re.sub(r"<[^>]+>", "", xml).strip()) < 200:
                    warnings.append("%s: văn bản dưới 200 ký tự" % did)
            except Exception:
                errors.append("%s: không đọc được docx" % did)
        if not d.get("title"):
            warnings.append("%s: chưa có title" % did)
        if not d.get("date"):
            warnings.append("%s: chưa có date" % did)

    for a in m.get("tep_dinh_kem", []):
        listed.add(a["file"])
        full = os.path.join(root, a["file"])
        if not os.path.isfile(full):
            errors.append("Tệp đính kèm không tồn tại: %s" % a["file"])
        elif sha256(full) != a.get("sha256"):
            errors.append("Tệp đính kèm sha256 không khớp: %s" % a["file"])

    for dp, _, fns in os.walk(root):
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/")
            if rel != "manifest.json" and rel not in listed:
                errors.append("File ngoài manifest: %s" % rel)

    for issue in m.get("van_de_ton_dong", []):
        warnings.append("Tồn đọng [%s] %s" % (issue.get("loai"), issue.get("id") or issue.get("zip_path") or ""))

    print("Hồ sơ %s: %d tài liệu, %d tệp đính kèm" % (ma, len(ids), len(m.get("tep_dinh_kem", []))))
    return errors, warnings


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    errs, warns = validate(sys.argv[1])
    for w in warns:
        print("CẢNH BÁO:", w)
    for e in errs:
        print("LỖI:", e)
    print("KẾT QUẢ: %s (%d lỗi, %d cảnh báo)" % ("ĐẠT" if not errs else "KHÔNG ĐẠT", len(errs), len(warns)))
    sys.exit(1 if errs else 0)
