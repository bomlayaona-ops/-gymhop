"""Philippine address helper: Region -> Province -> City/Municipality (+ a free-text description).
The list lives in static/data/ph_address.json, which the browser also uses for the dropdowns."""
import json
import os

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "data", "ph_address.json")
with open(_PATH, encoding="utf-8") as fh:
    DATA = json.load(fh)


def read_address(form):
    """Read region/province/city/city_other/detail from a submitted form.
    Returns (values, error). values has region, province, city, detail and full (one printable line)."""
    region = form.get("region", "").strip()
    province = form.get("province", "").strip()
    city = form.get("city", "").strip()
    other = form.get("city_other", "").strip()
    detail = form.get("detail", "").strip()
    values = {"region": region, "province": province, "city": city, "city_other": other, "detail": detail}
    if region not in DATA:
        return values, "Please choose your region."
    if province not in DATA[region]:
        return values, "Please choose a province from the list."
    if city == "__other__":
        if not 2 <= len(other) <= 80:
            return values, "Type your city or municipality (2 to 80 characters)."
        city = other
    elif city not in DATA[region][province]:
        return values, "Please choose your city or municipality."
    if not 5 <= len(detail) <= 150:
        return values, "Describe your address (house/unit no., street, barangay, landmark) in 5 to 150 characters."
    values["city"] = city
    values["full"] = f"{detail}, {city}, {province}, {region}"
    return values, None
