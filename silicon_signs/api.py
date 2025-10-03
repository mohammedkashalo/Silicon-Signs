import os, math, tempfile, re
import frappe, fitz  # PyMuPDF
from svgpathtools import svg2paths2
from xml.etree import ElementTree as ET

# ---- knobs ----
BEZ_TOL_PT = 0.25
MIN_SUBPATH_LEN_PT = 0.75

def _dist(p, q): return math.hypot(p.x - q.x, p.y - q.y)

def _cubic_len(p0, p1, p2, p3, tol=BEZ_TOL_PT, depth=0, max_depth=12):
    chord = _dist(p0, p3)
    cont  = _dist(p0, p1) + _dist(p1, p2) + _dist(p2, p3)
    if depth >= max_depth or abs(cont - chord) < tol:
        return (cont + chord) / 2.0
    m01 = fitz.Point((p0.x+p1.x)/2, (p0.y+p1.y)/2)
    m12 = fitz.Point((p1.x+p2.x)/2, (p1.y+p2.y)/2)
    m23 = fitz.Point((p2.x+p3.x)/2, (p2.y+p3.y)/2)
    m012 = fitz.Point((m01.x+m12.x)/2, (m01.y+m12.y)/2)
    m123 = fitz.Point((m12.x+m23.x)/2, (m12.y+m23.y)/2)
    m0123 = fitz.Point((m012.x+m123.x)/2, (m012.y+m123.y)/2)
    return (_cubic_len(p0, m01, m012, m0123, tol, depth+1, max_depth) +
            _cubic_len(m0123, m123, m23, p3, tol, depth+1, max_depth))

def _page_vector_length_points(page: fitz.Page, only_visible=False) -> float:
    total = 0.0
    drawings = page.get_drawings()  # list[dict]
    for d in drawings:
        if only_visible:
            stroke_alpha = d.get("stroke_opacity", 1.0)
            fill_alpha   = d.get("fill_opacity", 1.0)
            has_stroke   = d.get("color") is not None and stroke_alpha > 0
            has_fill     = d.get("fill") is not None and fill_alpha > 0
            if not (has_stroke or has_fill):
                continue
        items = d.get("items") or []
        cp = sp = None
        sub_len = 0.0
        for it in items:
            if not it: continue
            op = it[0]
            pts = it[1] if len(it) > 1 else []
            try:
                if op == "m":
                    if sub_len >= MIN_SUBPATH_LEN_PT: total += sub_len
                    sub_len = 0.0
                    cp = pts[0] if pts else None; sp = cp
                elif op == "l" and cp is not None and pts:
                    p1 = pts[0]; sub_len += _dist(cp, p1); cp = p1
                elif op == "c" and cp is not None and len(pts) >= 3:
                    sub_len += _cubic_len(cp, pts[0], pts[1], pts[2]); cp = pts[2]
                elif op == "h" and cp is not None and sp is not None:
                    sub_len += _dist(cp, sp); cp = sp
                elif op == "re" and pts:
                    r = pts[0]; sub_len += 2.0 * (abs(r.width) + abs(r.height))
            except Exception:
                continue
        if sub_len >= MIN_SUBPATH_LEN_PT: total += sub_len
    return total

# --- SVG fallback helpers ---
_UNIT_TO_IN = {'':1/96,'px':1/96,'in':1,'mm':1/25.4,'cm':1/2.54,'pt':1/72,'pc':1/6}
def _len_in_in(s):
    if not s: return None
    m = re.match(r'^\s*([+-]?\d+(?:\.\d+)?)\s*([a-z%]*)\s*$', s, re.I)
    if not m: return None
    val, unit = float(m.group(1)), (m.group(2) or '').lower()
    return val * _UNIT_TO_IN.get(unit, 1/96)

def _svg_inches_per_userunit(svg_path, page_w_pt=None, page_h_pt=None):
    root = ET.parse(svg_path).getroot()
    vb = root.get('viewBox') or root.get('viewbox')
    if vb:
        parts = [p for p in re.split(r'[, \s]+', vb.strip()) if p]
        if len(parts) == 4:
            _, _, vbw, vbh = map(float, parts)
            w_in = _len_in_in(root.get('width'))
            h_in = _len_in_in(root.get('height'))
            if w_in and vbw: return w_in / vbw
            if h_in and vbh: return h_in / vbh
            # use PDF page size if provided (points → inches)
            if page_w_pt and vbw: return (page_w_pt/72.0) / vbw
            if page_h_pt and vbh: return (page_h_pt/72.0) / vbh
    return 1/96  # last resort

@frappe.whitelist()
def calculate_perimeter(file_url: str, only_visible: int = 0):
    if not file_url:
        frappe.throw("Missing file URL.")
    # resolve file path
    rel = file_url.lstrip("/")
    src = None
    for base in ("public", "private"):
        cand = os.path.join(frappe.get_site_path(base), rel)
        if os.path.exists(cand): src = cand; break
        if rel.startswith("files/"):
            cand = os.path.join(frappe.get_site_path(base), rel)
            if os.path.exists(cand): src = cand; break
    if not src:
        cand = os.path.join(frappe.get_site_path("public"), rel.replace("/files/", "files/"))
        if os.path.exists(cand): src = cand
    if not src or not os.path.exists(src):
        frappe.throw(f"File not found: {file_url}")

    # open via PyMuPDF (AI/PDF)
    try:
        doc = fitz.open(src)
    except Exception as e:
        frappe.log_error(f"PyMuPDF open failed: {e}", "AI Perimeter")
        frappe.throw("Cannot open file with PDF engine. Ensure AI is PDF-compatible or export as PDF.")

    total_pts = 0.0
    ov = str(only_visible or "0").lower() in ("1","true","yes")
    try:
        for page in doc:
            total_pts += _page_vector_length_points(page, only_visible=ov)
    finally:
        # keep page size for SVG ipu if we need it
        sizes_pt = [(p.rect.width, p.rect.height) for p in doc]
        doc.close()

    # Primary result
    if total_pts > 0:
        per_in = round(total_pts / 72.0, 3)
        per_lf = round(per_in / 12.0, 3)
        frappe.log_error(f"AI/PDF perimeter | file={file_url} | pts={total_pts:.3f} | in={per_in} | LF={per_lf}", "AI Perimeter")
        return {"perimeter_inches": per_in, "perimeter_lf": per_lf, "source": "drawings"}

    # ---- Fallback A: full-page SVG render (includes text as paths) ----
    try:
        doc = fitz.open(src)
        page = doc[0]  # assume first page; sum more if needed
        svg_str = page.get_svg_image(text_as_path=True)
        page_w_pt, page_h_pt = page.rect.width, page.rect.height
        doc.close()

        # dump to temp, parse with svgpathtools
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False, encoding="utf-8") as tmp:
            tmp.write(svg_str)
            tmp_path = tmp.name

        paths, _, _ = svg2paths2(tmp_path)
        os.unlink(tmp_path)
        total_user = sum(p.length() for p in paths)
        ipu = _svg_inches_per_userunit(tmp_path, page_w_pt=page_w_pt, page_h_pt=page_h_pt)
        per_in = round(total_user * ipu, 3)
        per_lf = round(per_in / 12.0, 3)

        if per_in > 0:
            frappe.log_error(
                f"SVG fallback perimeter | file={file_url} | user_sum={total_user:.3f} | ipu={ipu:.6f} "
                f"| in={per_in} | LF={per_lf} | page_pt=({page_w_pt:.3f},{page_h_pt:.3f})",
                "AI Perimeter"
            )
            return {"perimeter_inches": per_in, "perimeter_lf": per_lf, "source": "svg_fallback"}
    except Exception as e:
        frappe.log_error(f"SVG fallback failed: {e}", "AI Perimeter")

    # Nothing measurable
    frappe.throw("Measured length is zero. The file may contain only raster images or non-vector content (or content hidden in unsupported constructs). Try exporting outlines from Illustrator or send a PDF-compatible AI.")
