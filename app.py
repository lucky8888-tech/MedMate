import re
import json
import os
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, send_from_directory
from medmate import suggest, load_data, INDICATIONS_MAP, get_indication, match_from_text
from scan import extract_text, is_ocr_available, tesseract_ready

app = Flask(__name__, static_folder="static", template_folder="templates")

# --- Configuration (overridable via environment variables) ---
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
# Local file where user feedback is stored. Never served publicly.
FEEDBACK_FILE = os.environ.get("FEEDBACK_FILE", "feedback.json")
FEEDBACK_MAX_LEN = 5000

def calculate_savings(prescribed_price_str, alt_price_str):
    """
    Parses prices (e.g. 'Rs. 45' vs 'Rs. 38') and calculates savings in Rs and percentage.
    """
    try:
        p_match = re.search(r'([\d\.]+)', prescribed_price_str or "")
        a_match = re.search(r'([\d\.]+)', alt_price_str or "")
        if p_match and a_match:
            p_val = float(p_match.group(1))
            a_val = float(a_match.group(1))
            diff = p_val - a_val
            if diff > 0 and p_val > 0:
                pct = round((diff / p_val) * 100)
                return {
                    "saves_money": True,
                    "savings_amount": f"Rs. {int(diff) if diff.is_integer() else diff}",
                    "savings_percent": f"{pct}% cheaper"
                }
            elif diff < 0:
                return {
                    "saves_money": False,
                    "savings_amount": f"Rs. {int(abs(diff)) if abs(diff).is_integer() else abs(diff)} more",
                    "savings_percent": ""
                }
    except Exception:
        pass
    return None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/manifest.json")
def manifest():
    return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

@app.route("/service-worker.js")
def service_worker():
    return send_from_directory("static", "service-worker.js", mimetype="application/javascript")

@app.route("/api/medicines", methods=["GET"])
def get_medicines():
    """
    Returns all medicines in database for live autocomplete search suggestions.
    """
    medicines, _ = load_data()
    results = []
    for med in medicines.values():
        results.append({
            "id": med["id"],
            "brand": med["brand"],
            "active_ingredients": med["active_ingredients"],
            "strength": med["strength"],
            "form": med["form"],
            "price": med["price_per_pack"],
            "used_for": get_indication(med["active_ingredients"])
        })
    return jsonify({"medicines": results})

@app.route("/api/common-allergies", methods=["GET"])
def get_common_allergies():
    """
    Returns curated list of common allergens for one-tap chip selection.
    """
    common = [
        {"name": "Dye R", "category": "Inactive Colorant"},
        {"name": "Gelatin", "category": "Inactive Binder"},
        {"name": "Starch", "category": "Inactive Filler"},
        {"name": "Lactose", "category": "Inactive Excipient"},
        {"name": "NSAID", "category": "Drug Class"},
        {"name": "Penicillin Antibiotic", "category": "Drug Class"},
        {"name": "Aspirin", "category": "Active Ingredient"},
        {"name": "Paracetamol", "category": "Active Ingredient"},
        {"name": "Titanium Dioxide", "category": "Inactive Pigment"}
    ]
    return jsonify({"allergies": common})

@app.route("/api/suggest", methods=["POST"])
def api_suggest():
    """
    Main API endpoint: evaluates medicine, patient allergies, and substitutions.
    """
    data = request.get_json(force=True, silent=True) or {}
    query = data.get("query", "").strip()
    allergies = data.get("allergies", [])
    do_not_substitute = bool(data.get("do_not_substitute", False))

    if not query:
        return jsonify({"error": "Please enter a medicine name or ID."}), 400

    result = suggest(query, allergies, do_not_substitute=do_not_substitute)

    if "error" in result:
        return jsonify({"error": result["error"]}), 404

    # Calculate savings for each alternative compared to prescribed product
    pres_med = result["prescribed"]
    medicines, _ = load_data()
    pres_price = None
    if pres_med["id"] in medicines:
        pres_price = medicines[pres_med["id"]]["price_per_pack"]

    for alt in result.get("alternatives", []):
        alt["used_for"] = get_indication(pres_med.get("active_ingredients", ""))
        if pres_price:
            alt["savings"] = calculate_savings(pres_price, alt.get("price_per_pack"))
        else:
            alt["savings"] = None

    return jsonify(result)


@app.route("/api/scan/status", methods=["GET"])
def api_scan_status():
    """Reports whether the OCR backend is available so the UI can adapt."""
    return jsonify({
        "ocr_available": is_ocr_available(),
        "binary_ready": tesseract_ready(),
    })


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """
    Camera/Scan endpoint: runs OCR on an uploaded medicine photo, matches the
    extracted text to the database, and (when possible) enriches the top match
    with full details + allergy-checked alternatives via the existing engine.

    Identification is based on printed label text only - never colour/appearance.
    Images are processed in memory and never stored or sent to third parties.
    """
    if "image" not in request.files:
        return jsonify({"error": "No image file provided."}), 400

    file = request.files["image"]
    image_bytes = file.read()
    if not image_bytes:
        return jsonify({"error": "The selected image is empty."}), 400

    # Patient allergies + do-not-substitute (shared with the text-search flow)
    allergies_raw = request.form.get("allergies", "[]")
    try:
        allergies = json.loads(allergies_raw) if allergies_raw else []
    except (ValueError, TypeError):
        allergies = []
    do_not_substitute = str(request.form.get("do_not_substitute", "")).lower() in ("1", "true", "yes")

    # Step 1: OCR (fails gracefully if Tesseract is missing)
    ocr = extract_text(image_bytes)
    if not ocr.get("available") or not ocr.get("binary_ready"):
        return jsonify({
            "error": ocr.get("error") or "OCR is not available on this server.",
            "ocr_available": ocr.get("available", False),
        }), 503

    if ocr.get("error") and not ocr.get("text"):
        return jsonify({"error": ocr["error"]}), 500

    # Step 2: Match extracted text to the medicine database
    match_result = match_from_text(ocr["text"])
    matches = match_result["matches"]

    response = {
        "extracted_text": ocr["text"],
        "ocr_confidence": ocr["confidence"],
        "strengths_found": match_result["strengths_found"],
        "uncertain": match_result["uncertain"],
        "warning": match_result["warning"],
        "matches": [
            {
                "id": m["id"],
                "brand": m["brand"],
                "active_ingredients": m["active_ingredients"],
                "strength": m["strength"],
                "form": m["form"],
                "price_per_pack": m["price_per_pack"],
                "used_for": m["used_for"],
                "score": m["score"],
                "signals": m["signals"],
            }
            for m in matches[:5]
        ],
        "suggest_result": None,
    }

    # Step 3: Enrich the top match with full engine details + allergy-checked
    # alternatives so the scan reuses the exact same logic as /api/suggest.
    if matches:
        top_brand = matches[0]["brand"]
        suggest_result = suggest(top_brand, allergies, do_not_substitute=do_not_substitute)

        if "error" not in suggest_result:
            medicines, _ = load_data()
            pres_id = suggest_result["prescribed"]["id"]
            pres_price = medicines.get(pres_id, {}).get("price_per_pack")
            for alt in suggest_result.get("alternatives", []):
                alt["used_for"] = get_indication(
                    suggest_result["prescribed"].get("active_ingredients", "")
                )
                alt["savings"] = calculate_savings(pres_price, alt.get("price_per_pack")) if pres_price else None
            response["suggest_result"] = suggest_result

    return jsonify(response)


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """
    Stores user feedback to a local JSON file on the server.

    No personally identifiable information is required (name/email are optional),
    and there is no public read endpoint, so submitted details are not exposed.
    """
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Please enter a message."}), 400
    if len(message) > FEEDBACK_MAX_LEN:
        return jsonify({"error": f"Message is too long (max {FEEDBACK_MAX_LEN} characters)."}), 400

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "category": (data.get("category") or "general").strip()[:50],
        "message": message,
        # Optional fields - stored locally, never served back publicly.
        "name": (data.get("name") or "").strip()[:100],
        "email": (data.get("email") or "").strip()[:150],
    }

    try:
        existing = []
        if os.path.exists(FEEDBACK_FILE):
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                try:
                    existing = json.load(f)
                except json.JSONDecodeError:
                    existing = []
        existing.append(entry)
        tmp = FEEDBACK_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)
        os.replace(tmp, FEEDBACK_FILE)
    except OSError:
        return jsonify({"error": "Could not save feedback at this time."}), 500

    return jsonify({"success": True, "message": "Thank you for your feedback!"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1")
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print("\n" + "=" * 60)
    print("            SAFEDOSE WEB APP            ")
    print(f"      Access at: http://{host}:{port}          ")
    print("=" * 60 + "\n")
    app.run(host=host, port=port, debug=debug)
