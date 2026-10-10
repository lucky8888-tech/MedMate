import csv
import json
import re

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
            medicines_file="medicines.csv", classes_file="allergy_classes.csv"):
    """
    Main function required by project spec.
    Takes a prescribed medicine ID, allergy list, and substitution flag,
    then returns alternatives, excluded options, and safety flags as a dictionary/JSON.
    """
    medicines, ingredient_to_class = load_data(medicines_file, classes_file)
    allergy_set = {normalize_str(a) for a in allergies}

    # Validate medicine existence
    if medicine_id not in medicines:
        return {"error": f"Medicine ID '{medicine_id}' not found in database."}

    prescribed = medicines[medicine_id]
    
    # Safety Rule 4: Prescribed medicine allergy self-check
    prescribed_flags = []
    has_prescribed_trigger, prescribed_reasons = check_allergy_triggers(
        prescribed, allergy_set, ingredient_to_class
    )
    if has_prescribed_trigger:
        prescribed_flags.append(
            f"ALERT: Prescribed product matches allergy triggers: {', '.join(prescribed_reasons)}. Check with doctor."
        )

    response = {
        "prescribed": {
            "id": prescribed["id"],
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
    target_strength = normalize_strength(prescribed["strength"])
    target_form = normalize_str(prescribed["form"])

    # Scan dataset for candidates
    for cand_id, cand in medicines.items():
        if cand_id == medicine_id:
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

if __name__ == "__main__":
    # Test Crocin 500 with no allergies
    result = suggest("M009", [])
    print(json.dumps(result, indent=2))