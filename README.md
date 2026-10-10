# MedMate - Medicine Alternative Suggester with Allergy Check

MedMate is a rule-based Python application that identifies safe medicine alternatives while evaluating direct, drug-class, and inactive ingredient allergy triggers.

> **Disclaimer:** MedMate uses fictional data for educational purposes only. It is not medical advice.

---

## Completed Levels
- [x] **Level 1:** Search and details lookup from CSV datasets
- [x] **Level 2:** Strict alternative matching and side-by-side difference breakdown
- [x] **Level 3:** 3-tier allergy check engine (Direct, Drug-Class, and Inactive)
- [x] **Level 4:** Enforced 5 Safety Rules & comprehensive unit testing

---

## Implemented Safety Rules
1. **Strict Matching:** Only suggests products matching exact active ingredient(s), strength (unit-normalized), and form.
2. **Missing Data Handling:** Excludes products with missing inactive ingredient data when an allergy list is present.
3. **Do Not Substitute Flag:** Rejects substitution requests when explicitly flagged.
4. **Prescribed Product Warning:** Alerts the user if the prescribed medicine itself matches their allergy list.
5. **Clear Language:** Avoids absolute terms like "safe", declaring only: *"No listed trigger found in the data provided."*

---

## How to Run

### Run Core Logic:
```bash
python medmate.py