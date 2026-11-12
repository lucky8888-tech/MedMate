import csv
import difflib
import json
import re
import urllib.request
import urllib.parse
import urllib.error

def normalize_str(text: str) -> str:
    """Standardizes text for clean, case-insensitive, and whitespace-tolerant comparisons."""
    return text.strip().lower() if text else ""

def normalize_strength(strength_str: str) -> str:
    """
    Standardizes strength values so different formats can be accurately matched.
    Example: Converts '0.5 g' to '500 mg' and handles combination products like '500 mg + 10 mg'.
    """
    parts = [p.strip() for p in strength_str.split('+')]
    normalized_parts = []
    
    for part in parts:
        match = re.match(r"^([\d\.]+)\s*([a-zA-Z]+)$", part)
        if match:
            val, unit = float(match.group(1)), match.group(2).lower()
            if unit == "g":
                val = val * 1000
                unit = "mg"
            # Format cleanly as integer if it's a whole number
            val_str = f"{int(val)}" if val.is_integer() else f"{val}"
            normalized_parts.append(f"{val_str} {unit}")
        else:
            normalized_parts.append(part.lower())
            
    return " + ".join(normalized_parts)

def load_data(medicines_file="medicines.csv", classes_file="allergy_classes.csv"):
    """
    Reads the CSV files and transforms them into Python dictionaries for quick lookup.
    """
    medicines = {}
    with open(medicines_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            medicines[row["id"].strip()] = row

    ingredient_to_class = {}
    with open(classes_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ingredient_to_class[normalize_str(row["ingredient"])] = normalize_str(row["class"])

    return medicines, ingredient_to_class

# International drug synonyms mapping (e.g., US vs International names)
DRUG_SYNONYMS = {
    "paracetamol": "acetaminophen",
    "acetaminophen": "paracetamol",
    "salbutamol": "albuterol",
    "albuterol": "salbutamol",
}

# Medical indications, uses, and conditions treated
INDICATIONS_MAP = {
    "paracetamol": "Fever reduction, headache, toothache, and mild-to-moderate pain relief.",
    "ibuprofen + paracetamol": "Inflammatory pain relief, fever, muscle aches, joint pain, and dental pain.",
    "amoxicillin + clavulanic acid": "Bacterial infections (ear, sinus, throat, chest, skin, and urinary tract infections).",
    "azithromycin": "Bacterial infections, bronchitis, pneumonia, tonsillitis, ear/throat infections.",
    "pantoprazole": "Acidity, heartburn, acid reflux (GERD), and stomach/peptic ulcers.",
    "omeprazole": "Heartburn, acid reflux, stomach indigestion, and peptic ulcers.",
    "cetirizine": "Allergic symptoms (sneezing, runny nose, watery eyes, skin itching, and hives).",
    "levocetirizine": "Allergic rhinitis, hay fever, seasonal allergies, and chronic skin urticaria.",
    "metformin": "Type 2 diabetes (helps regulate and lower blood glucose/sugar levels).",
    "amlodipine": "Hypertension (high blood pressure) and prevention of angina (chest pain).",
    "telmisartan": "Hypertension (high blood pressure) and reduction of cardiovascular risk.",
    "aceclofenac + paracetamol": "Pain and swelling associated with arthritis, joint pain, backache, and injuries.",
    "dicyclomine + mefenamic acid": "Abdominal cramps, stomach spasms, and menstrual pain (period cramps).",
    "magnesium hydroxide + aluminium hydroxide": "Fast relief from stomach acidity, heartburn, and acid indigestion.",
    "fexofenadine": "Non-drowsy allergy relief (hay fever, seasonal allergies, and itchy skin hives).",
    "aspirin": "Headache, pain relief, fever, and blood clot prevention (cardioprotective).",
    "paracetamol + phenylephrine + chlorpheniramine": "Common cold symptoms, nasal congestion, runny nose, sneezing, and fever.",
    "zolvexol": "Pain management and general analgesic relief."
}

def get_indication(active_ingredients: str) -> str:
    """Returns the disease, condition, or medical purpose for an active ingredient or combination."""
    if not active_ingredients:
        return "Therapeutic medication; consult your doctor or pharmacist for specific use."

    norm = " + ".join(sorted([a.strip().lower() for a in active_ingredients.split("+")]))
    for key, text in INDICATIONS_MAP.items():
        key_norm = " + ".join(sorted([k.strip().lower() for k in key.split("+")]))
        if norm == key_norm:
            return text

    # Individual ingredient fallback
    for act in active_ingredients.split("+"):
        act_clean = act.strip().lower()
        if act_clean in INDICATIONS_MAP:
            return INDICATIONS_MAP[act_clean]

    return "Therapeutic medication; consult your doctor or pharmacist for specific use."


def fetch_openfda(query: str, timeout: int = 6):
    """
    Step 1: Queries the public openFDA API for a medicine by brand, generic, or substance name.
    Supports international drug synonyms (e.g., Paracetamol -> Acetaminophen).
    Returns the first matching result dictionary, or None if not found or network fails.
    """
    if not query:
        return None

    # Check for international synonyms (e.g. Paracetamol -> Acetaminophen in US FDA)
    q_norm = query.strip().lower()
    search_term = DRUG_SYNONYMS.get(q_norm, query.strip())

    # Search brand_name, generic_name, and substance_name
    encoded_query = urllib.parse.quote(
        f'openfda.brand_name:"{search_term}" openfda.generic_name:"{search_term}" openfda.substance_name:"{search_term}"'
    )
    url = f"https://api.fda.gov/drug/label.json?search={encoded_query}&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "MedMate/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            results = data.get("results", [])
            return results[0] if results else None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception):
        # Gracefully handle 404 (not found), timeouts, or no internet connection
        return None

def parse_fda_label(label_data: dict) -> dict:
    """
    Step 2: Parses raw openFDA drug label JSON into MedMate's standardized medicine dictionary format.
    Extracts brand, active ingredients, dosage form, manufacturer, and inactive ingredients.
    """
    if not label_data:
        return {}

    openfda = label_data.get("openfda", {})

    # Brand and generic names
    brand = openfda.get("brand_name", ["Unknown Brand"])[0]
    generic = openfda.get("generic_name", [""])[0]

    # Active ingredients: prefer standardized substance_name, fallback to generic
    substances = openfda.get("substance_name", [])
    if substances:
        active_ingredients = " + ".join([s.title() for s in substances])
    elif generic:
        active_ingredients = generic.title()
    else:
        active_ingredients = "Unknown"

    # Manufacturer
    manufacturer = openfda.get("manufacturer_name", ["FDA Registered Manufacturer"])[0]

    # Dosage form
    dosage_form = openfda.get("dosage_form", ["tablet"])[0] if openfda.get("dosage_form") else "tablet"

    # Inactive ingredients (excipients)
    raw_inactives = label_data.get("inactive_ingredient", [])
    inactive_list = []
    if raw_inactives:
        text = " ".join(raw_inactives) if isinstance(raw_inactives, list) else str(raw_inactives)
        # Strip leading phrases like "Inactive ingredients:"
        cleaned = re.sub(r'^(?:inactive\s+ingredients?[\s\:\.\u200b]*)+', '', text, flags=re.IGNORECASE)
        # Split by comma or semicolon
        items = [re.sub(r'\s+', ' ', item).strip().strip('.') for item in re.split(r'[,;]', cleaned)]
        inactive_list = [i for i in items if i and len(i) > 1]

    # Drug class (EPC - Established Pharmacologic Class)
    pharm_classes = openfda.get("pharm_class_epc", [])

    # Purpose or medical indications
    purpose_list = label_data.get("purpose", [])
    indications_list = label_data.get("indications_and_usage", [])
    fda_indication = ""
    if purpose_list:
        raw_p = " ".join(purpose_list)
        cleaned_p = re.sub(r'^(?:purposes?[\s\:\.\u200b]*)+', '', raw_p, flags=re.IGNORECASE).strip()
        # Deduplicate repeated phrases (e.g. 'Pain reliever Pain reliever' -> 'Pain reliever')
        deduped = re.sub(r'\b(\w+(?:\s+\w+)?)\s+\1\b', r'\1', cleaned_p, flags=re.IGNORECASE)
        fda_indication = re.sub(r'\s+', ' ', deduped).strip()
    elif indications_list:
        raw_ind = " ".join(indications_list)
        first_sentence = raw_ind.split(".")[0].strip()
        fda_indication = re.sub(r'[\u200b\s]+', ' ', first_sentence)

    if not fda_indication:
        fda_indication = get_indication(active_ingredients)

    return {
        "id": f"FDA-{brand.split()[0].upper()}",
        "brand": brand,
        "active_ingredients": active_ingredients,
        "strength": "See Label",
        "form": dosage_form.lower(),
        "inactive_ingredients": "; ".join(inactive_list),
        "manufacturer": manufacturer,
        "pack_size": "FDA Listed",
        "price_per_pack": "N/A (US Market)",
        "pharm_classes": pharm_classes,
        "indications": fda_indication,
        "source": "openFDA"
    }

def check_allergy_triggers(medicine, allergy_set, ingredient_to_class):
    """
    Evaluates direct, drug-class, and inactive ingredient allergy triggers for a medicine.
    Returns: (has_trigger, list_of_reasons)
    """
    reasons = []
    
    # 1. Direct Active Ingredient & Drug-Class Check
    raw_actives = [a.strip() for a in medicine["active_ingredients"].split("+")]
    for act in raw_actives:
        act_norm = normalize_str(act)
        
        # Direct Trigger Check
        if act_norm in allergy_set:
            reasons.append(f"active ingredient '{act}' is on your allergy list")
            
        # Drug-Class Trigger Check
        drug_class = ingredient_to_class.get(act_norm)
        if drug_class and drug_class in allergy_set:
            reasons.append(f"active ingredient '{act}' belongs to allergic drug class '{drug_class}'")

    # 2. Inactive Ingredient Check
    raw_inactives = medicine.get("inactive_ingredients", "").strip()
    if raw_inactives and raw_inactives.upper() != "NONE":
        inactives = [i.strip() for i in raw_inactives.split(";")]
        for inact in inactives:
            if normalize_str(inact) in allergy_set:
                reasons.append(f"inactive ingredient '{inact}' is on your allergy list")

    return len(reasons) > 0, reasons

def suggest(medicine_id, allergies, do_not_substitute=False, 
            medicines_file="medicines.csv", classes_file="allergy_classes.csv",
            use_openfda=True):
    """
    Main function required by project spec.
    Takes a prescribed medicine ID or brand name, allergy list, and substitution flag,
    then returns alternatives, excluded options, and safety flags as a dictionary/JSON.
    Supports local CSV dataset lookup and live openFDA online fallback.
    """
    medicines, ingredient_to_class = load_data(medicines_file, classes_file)
    allergy_set = {normalize_str(a) for a in allergies}

    prescribed = None
    prescribed_source = "Local Database"

    # 1. Search by exact ID (e.g., 'M001')
    query_clean = medicine_id.strip()
    query_upper = query_clean.upper()
    if query_upper in medicines:
        prescribed = medicines[query_upper]
    else:
        # 2a. Search by local brand name (e.g., 'Combiflam', 'crocin', 'dolo')
        query_norm = normalize_str(query_clean)
        for med in medicines.values():
            brand_norm = normalize_str(med["brand"])
            if query_norm == brand_norm or query_norm in brand_norm:
                prescribed = med
                break

        # 2b. Search by local active ingredients (e.g., 'Paracetamol', 'Aspirin', 'Ibuprofen')
        if not prescribed:
            query_alias = DRUG_SYNONYMS.get(query_norm, query_norm)
            for med in medicines.values():
                actives_norm = normalize_str(med["active_ingredients"])
                if query_norm in actives_norm or query_alias in actives_norm:
                    prescribed = med
                    break

        # 2c. Fuzzy matching for typos (e.g., 'dollo' -> 'Dolo 650', 'combflam' -> 'Combiflam')
        if not prescribed:
            best_score = 0
            best_match = None
            for med in medicines.values():
                brand_norm = normalize_str(med["brand"])
                words = brand_norm.split()
                scores = [difflib.SequenceMatcher(None, query_norm, brand_norm).ratio()]
                for w in words:
                    scores.append(difflib.SequenceMatcher(None, query_norm, w).ratio())

                for act in med["active_ingredients"].split("+"):
                    scores.append(difflib.SequenceMatcher(None, query_norm, normalize_str(act)).ratio())
                    for act_w in normalize_str(act).split():
                        scores.append(difflib.SequenceMatcher(None, query_norm, act_w).ratio())

                max_for_med = max(scores)
                if max_for_med > best_score:
                    best_score = max_for_med
                    best_match = med

            if best_score >= 0.72 and best_match:
                prescribed = best_match
                prescribed_source = f"Local Database (Matched '{medicine_id}' to '{best_match['brand']}')"

    # 3. If not found locally, query live openFDA API
    if not prescribed and use_openfda:
        fda_data = fetch_openfda(query_clean)
        if fda_data:
            prescribed = parse_fda_label(fda_data)
            prescribed_source = "openFDA (Live API)"

    # Validate medicine existence
    if not prescribed:
        return {"error": f"Medicine '{medicine_id}' not found in database or openFDA."}

    # Safety Rule 4: Prescribed medicine allergy self-check
    prescribed_flags = []
    has_prescribed_trigger, prescribed_reasons = check_allergy_triggers(
        prescribed, allergy_set, ingredient_to_class
    )
    if has_prescribed_trigger:
        prescribed_flags.append(
            f"ALERT: Prescribed product matches allergy triggers: {', '.join(prescribed_reasons)}. Check with doctor."
        )

    indications = prescribed.get("indications") or get_indication(prescribed.get("active_ingredients", ""))

    response = {
        "prescribed": {
            "id": prescribed["id"],
            "brand": prescribed["brand"],
            "active_ingredients": prescribed["active_ingredients"],
            "indications": indications,
            "source": prescribed_source,
            "flags": prescribed_flags
        },
        "alternatives": [],
        "excluded": [],
        "message": ""
    }

    # Safety Rule 3: Check 'Do Not Substitute' flag
    if do_not_substitute:
        response["message"] = "Prescription is marked 'Do Not Substitute'. No alternatives suggested."
        return response

    # Extract target specifications for strict matching
    target_actives = sorted([normalize_str(a) for a in prescribed["active_ingredients"].split("+")])
    target_strength = normalize_strength(prescribed.get("strength", ""))
    target_form = normalize_str(prescribed.get("form", ""))

    # Scan dataset for candidates
    for cand_id, cand in medicines.items():
        if cand_id == prescribed.get("id"):
            continue  # Exclude self from alternatives

        # Safety Rule 1: Matching Rule (Active Ingredients, Strength, Form)
        cand_actives = sorted([normalize_str(a) for a in cand["active_ingredients"].split("+")])
        cand_strength = normalize_strength(cand["strength"])
        cand_form = normalize_str(cand["form"])

        if cand_actives != target_actives or cand_strength != target_strength or cand_form != target_form:
            continue  # Mismatched products are not alternatives

        # Safety Rule 2: Missing Inactive Data Check
        raw_inactives = cand.get("inactive_ingredients", "").strip()
        is_inactive_missing = (raw_inactives == "")

        if len(allergy_set) > 0 and is_inactive_missing:
            response["excluded"].append({
                "id": cand_id,
                "reason": "inactive ingredient data missing; cannot check allergies"
            })
            continue

        # Check Allergy Triggers (Direct, Class, Inactive)
        has_trigger, reasons = check_allergy_triggers(cand, allergy_set, ingredient_to_class)
        if has_trigger:
            response["excluded"].append({
                "id": cand_id,
                "reason": '; '.join(reasons)
            })
            continue

        # Add valid alternative with Difference Table details
        response["alternatives"].append({
            "id": cand_id,
            "brand": cand["brand"],
            "manufacturer": cand["manufacturer"],
            "pack_size": cand["pack_size"],
            "price_per_pack": cand["price_per_pack"],
            "inactive_ingredients": cand["inactive_ingredients"],
            "safety_note": "No listed trigger found in the data provided."  # Safety Rule 5
        })

    # Summary messaging
    if not response["alternatives"]:
        response["message"] = "No alternatives could be confirmed from the data provided. Ask your pharmacist."

    return response


def match_from_text(text, medicines_file="medicines.csv", classes_file="allergy_classes.csv"):
    """
    Matches raw OCR-extracted text against the medicine database.

    Identification is based ONLY on printed label text (brand names, active
    ingredients, and strength). It never uses colour, shape, or appearance.

    Returns a dict:
      - matches: list of candidate medicines (highest score first), each with
        id, brand, active_ingredients, strength, form, price_per_pack,
        used_for, score, signals
      - extracted_text: the input text (echoed for display)
      - strengths_found: strength strings read from the text
      - uncertain: bool
      - warning: str or None  (shown to the user when identification is unclear)
    """
    medicines, _ = load_data(medicines_file, classes_file)
    norm_text = normalize_str(text)
    tokens = set(re.findall(r"[a-z0-9]+", norm_text))

    # Strengths like "500 mg", "10 mg", "650 mg", "0.5 g"
    strengths_found = []
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(mg|g|mcg|ml)\b", norm_text):
        strengths_found.append(f"{m.group(1)} {m.group(2)}")

    candidates = []
    for med_id, med in medicines.items():
        brand = med["brand"]
        brand_norm = normalize_str(brand)
        actives = [a.strip() for a in med["active_ingredients"].split("+")]
        actives_norm = [normalize_str(a) for a in actives]

        score = 0
        signals = []

        # 1) Brand name (strongest signal). Match the full brand phrase first,
        #    then fall back to distinctive multi-character brand tokens.
        if brand_norm and len(brand_norm) >= 3 and brand_norm in norm_text:
            score += 50
            signals.append("brand name")
        else:
            brand_tokens = [t for t in brand_norm.split() if len(t) >= 4]
            if brand_tokens and all(t in tokens for t in brand_tokens):
                score += 40
                signals.append("brand name")

        # 2) Active ingredients (strong signal; multi-word actives matched as phrases)
        for act_n in actives_norm:
            if act_n and act_n in norm_text:
                score += 30
                if "active ingredient" not in signals:
                    signals.append("active ingredient")

        # 3) Strength (supporting signal; must match the candidate's normalized strength)
        if strengths_found:
            med_strength_norm = normalize_strength(med["strength"])
            found_norm = []
            for s in strengths_found:
                try:
                    found_norm.append(normalize_strength(s))
                except Exception:
                    found_norm.append(normalize_str(s))
            # Direct full-strength match, or all parts of a combination present
            if med_strength_norm in found_norm:
                score += 20
                signals.append("strength")
            else:
                parts = [p.strip() for p in med_strength_norm.split("+")]
                if len(parts) > 1 and all(p in found_norm for p in parts):
                    score += 20
                    signals.append("strength")

        if score > 0:
            candidates.append({
                "id": med_id,
                "brand": brand,
                "active_ingredients": med["active_ingredients"],
                "strength": med["strength"],
                "form": med["form"],
                "price_per_pack": med["price_per_pack"],
                "used_for": get_indication(med["active_ingredients"]),
                "score": score,
                "signals": signals,
            })

    candidates.sort(key=lambda c: c["score"], reverse=True)

    uncertain = True
    warning = None
    top = candidates[0] if candidates else None

    if not candidates:
        uncertain = True
        warning = ("No recognizable medicine name or ingredient was found in the captured text. "
                   "SafeDose identifies medicines from printed label text only, never by colour or "
                   "appearance. Please verify with your pharmacist.")
    elif len(candidates) >= 2 and candidates[0]["score"] == candidates[1]["score"]:
        uncertain = True
        warning = ("Several medicines matched the captured text with similar confidence, so the "
                   "identification is unclear. Please verify with your pharmacist.")
    elif top["score"] < 70:
        uncertain = True
        warning = ("Only a partial match was found in the captured text, so the identification is "
                   "unclear. Please verify with your pharmacist.")
    else:
        uncertain = False
        # Even when fairly confident, flag if no strength was read to corroborate
        if "strength" not in top["signals"]:
            warning = ("Matched on printed name, but the strength was not clearly read from the "
                       "label. Confirm the exact strength with your pharmacist before use.")

    return {
        "matches": candidates,
        "extracted_text": text,
        "strengths_found": strengths_found,
        "uncertain": uncertain,
        "warning": warning,
    }


def interactive_cli():
    """
    Runs an interactive command-line interface for MedMate.
    Prompts the user for medicine ID or name, patient allergies, and substitution preference.
    """
    print("=" * 60)
    print("        MEDMATE - Medicine Alternative Suggester        ")
    print("=" * 60)
    print("Type 'q' or 'exit' at the medicine prompt to quit.\n")

    while True:
        try:
            med_query = input("Enter Prescribed Medicine ID or Name (e.g., M001, Combiflam, Advil): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nThank you for using MedMate. Stay safe and healthy!")
            break

        if not med_query:
            print("[!] Please enter a medicine ID or name.\n")
            continue

        if med_query.lower() in ("q", "quit", "exit"):
            print("\nThank you for using MedMate. Stay safe and healthy!")
            break

        # Prompt for allergies
        try:
            allergies_raw = input("Enter allergies separated by commas (or press Enter if none): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nThank you for using MedMate. Stay safe and healthy!")
            break

        allergies = [a.strip() for a in allergies_raw.split(",") if a.strip()] if allergies_raw else []

        # Prompt for Do Not Substitute
        try:
            dns_raw = input("Is prescription marked 'Do Not Substitute'? (y/n, default: n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nThank you for using MedMate. Stay safe and healthy!")
            break

        do_not_substitute = dns_raw in ("y", "yes", "true", "1")

        # Run core suggest engine
        result = suggest(med_query, allergies, do_not_substitute)

        print("-" * 60)
        # Check for error (e.g., medicine not found)
        if "error" in result:
            print(f"[!] Error: {result['error']}")
            print("-" * 60 + "\n")
            continue

        # Prescribed Medicine Status
        pres = result["prescribed"]
        source_str = f" [{pres.get('source')}]" if pres.get("source") else ""
        print(f"[PRESCRIBED MEDICINE] {pres.get('brand', '')} (ID: {pres['id']}){source_str}")
        if pres.get("active_ingredients"):
            print(f"  Actives : {pres['active_ingredients']}")
        if pres.get("indications"):
            print(f"  Used For: {pres['indications']}")
        if pres['flags']:
            for flag in pres['flags']:
                print(f"  [!] {flag}")
        else:
            print("  Status  : No allergy triggers found for prescribed medicine.")

        # Do Not Substitute Notice
        if do_not_substitute and result.get("message"):
            print(f"\n[!] Notice: {result['message']}")
            print("-" * 60 + "\n")
            continue

        # Alternatives
        print("\n[RECOMMENDED ALTERNATIVES]")
        if result["alternatives"]:
            for alt in result["alternatives"]:
                print(f"  * {alt['brand']} ({alt['id']}) - Manufactured by: {alt['manufacturer']}")
                print(f"    - Pack Size : {alt['pack_size']}")
                print(f"    - Price     : {alt['price_per_pack']}")
                print(f"    - Inactives : {alt['inactive_ingredients']}")
                print(f"    - Note      : {alt['safety_note']}")
        else:
            msg = result.get("message") or "No alternatives could be confirmed from the data provided."
            print(f"  {msg}")

        # Excluded Options
        if result["excluded"]:
            print("\n[EXCLUDED CANDIDATES]")
            for exc in result["excluded"]:
                print(f"  * {exc['id']}: {exc['reason']}")

        print("-" * 60 + "\n")

if __name__ == "__main__":
    interactive_cli()