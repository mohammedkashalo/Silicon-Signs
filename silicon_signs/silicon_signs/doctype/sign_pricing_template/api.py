import frappe

def _round_to(x: float, step: float | None):
    if not step or step == "None":
        return float(x)
    step = float(step)
    return round(float(x) / step) * step

def _matches(rule, val):
    op = (rule.operator or "Equals").strip()
    if op == "Is Set":
        return val not in (None, "", 0)
    if op == "Equals":
        return (str(val) == str(rule.value))
    if op == "Not Equals":
        return (str(val) != str(rule.value))
    if op == "Between":
        try:
            v = float(val or 0)
            mn = float(rule.min_value if rule.min_value is not None else -1e30)
            mx = float(rule.max_value if rule.max_value is not None else 1e30)
            return mn <= v <= mx
        except Exception:
            return False
    return False

@frappe.whitelist()
def price_item_by_attributes(item_template: str, attributes, profile_name: str | None = None, currency: str | None = None):
    """Compute price solely from Item Attributes."""
    attrs = frappe.parse_json(attributes) if isinstance(attributes, str) else (attributes or {})

    if profile_name:
        profile = frappe.get_doc("Sign Pricing Template", profile_name)
    else:
        profile = frappe.get_all("Sign Pricing Template",
                                 filters={"sign_template": item_template},
                                 fields=["name"], limit=1)
        if not profile:
            frappe.throw(f"No Sign Pricing Template found for template {item_template}")
        profile = frappe.get_doc("Sign Pricing Template", profile[0].name)

    subtotal = float(profile.base_price or 0)
    breakdown = []
    # child table is `rules`
    for r in profile.rules:
        if not r.active:
            continue
        val = attrs.get(r.attribute)  # attribute keys are *Item Attribute* names
        if not _matches(r, val):
            continue

        mode = (r.mode or "Fixed").strip()
        before = subtotal

        if mode == "Fixed":
            subtotal += float(r.amount or 0)

        elif mode == "Percent":
            subtotal += subtotal * (float(r.amount or 0) / 100.0)

        elif mode == "Per Unit":
            qty = 0.0
            try:
                qty = float(val or 0)
            except Exception:
                qty = 0.0
            subtotal += qty * float(r.rate or 0)

        # breakdown line
        delta = subtotal - before
        label = r.notes or f"{r.attribute} {mode}"
        if abs(delta) > 1e-9:
            breakdown.append(f"{label}: {delta:+.2f}")

    rounded = _round_to(subtotal, profile.rounding)
    cur = currency or frappe.db.get_single_value("Global Defaults", "default_currency") or "USD"
    return {"price": float(rounded), "currency": cur, "breakdown": breakdown}