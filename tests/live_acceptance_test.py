"""Live acceptance test: exercise the full pipeline with the real marksheet."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.documents import process_uploads, propose_profile
from backend.profile import default_profile, merge_profile

MARKSHEET = r"C:\Users\Filxa\Documents\Qoder\EduPath AI\dc8d1b01\data\realistic_marksheet.png"

EXPECTED = {
    "name": "AHMAD RAZA KHAN",
    "father_name": "MUHAMMAD RAZA KHAN",
    "roll_number": "123456",
    "qualification": "HSSC",
    "board": None,
    "hssc_group": "Pre-Engineering",
    "hssc_percentage": 77.73,
    "aggregate": 77.73,
    "total_marks": 1100,
    "obtained_marks": 855,
}


def stage(label: str) -> None:
    print(f"\n{'='*60}")
    print(f"  STAGE: {label}")
    print(f"{'='*60}")


def main() -> None:
    if not os.path.isfile(MARKSHEET):
        print(f"ERROR: marksheet not found at {MARKSHEET}")
        sys.exit(1)

    with open(MARKSHEET, "rb") as f:
        raw_bytes = f.read()

    upload_bytes = [("realistic_marksheet.png", raw_bytes)]

    # -- Stage 1: process_uploads (OCR + field extraction) --
    stage("1. process_uploads() -- OCR + field extraction")
    docs = process_uploads(upload_bytes)

    for doc in docs:
        print(f"  filename:          {doc.filename}")
        print(f"  extraction_method: {doc.extraction_method}")
        print(f"  canonical_category:{doc.canonical_category}")
        print(f"  validation.valid:  {doc.validation.valid}")
        print(f"  validation.errors: {doc.validation.errors}")
        print(f"  validation.warnings: {doc.validation.warnings}")
        print(f"  raw_text length:   {len(doc.raw_text)} chars")
        print(f"  fields count:      {len(doc.fields)}")
        print()
        print("  --- Raw OCR Text (first 800 chars) ---")
        print(doc.raw_text[:800])
        print()
        print("  --- Extracted Fields ---")
        for field in doc.fields:
            print(f"    {field.field:25s} = {field.value!r}  (method={field.extraction_method})")
        print()

        field_map = {f.field: f.value for f in doc.fields}
        print("  --- Field Coverage Check ---")
        all_found = True
        for key, expected_val in EXPECTED.items():
            actual = field_map.get(key)
            if actual is not None:
                match = "OK" if str(actual) == str(expected_val) else f"MISMATCH (expected {expected_val!r})"
                print(f"    {key:25s} = {actual!r}  [{match}]")
            else:
                print(f"    {key:25s} = MISSING  [expected {expected_val!r}]")
                all_found = False
        if all_found:
            print("    ALL FIELDS EXTRACTED SUCCESSFULLY")
        else:
            print("    SOME FIELDS MISSING -- see above")

    # -- Stage 2: propose_profile (merge_documents) --
    stage("2. propose_profile() -- merge_documents")
    proposal = propose_profile(docs)
    print(f"  proposal.documents:  {proposal.documents}")
    print(f"  proposal.warnings:   {proposal.warnings}")
    print()
    print("  --- Profile dict ---")
    profile = proposal.profile
    for key in ["name", "father_name", "qualification", "board", "aggregate",
                 "total_marks", "obtained_marks", "roll_number", "hssc_group",
                 "ssc_percentage", "hssc_percentage"]:
        val = profile.get(key)
        expected_val = EXPECTED.get(key)
        if val is not None:
            match = "OK" if str(val) == str(expected_val) else f"MISMATCH (expected {expected_val!r})"
            print(f"    {key:25s} = {val!r}  [{match}]")
        else:
            print(f"    {key:25s} = {val!r}  [expected {expected_val!r}]")

    # -- Stage 3: merge_profile (what update_profile does internally) --
    stage("3. merge_profile() -- write to state (simulated)")
    base = default_profile()
    final_profile = merge_profile(base, profile, source="ocr")
    print("  --- Final student_profile ---")
    for key in ["name", "father_name", "qualification", "board", "aggregate",
                 "total_marks", "obtained_marks", "roll_number", "hssc_group",
                 "ssc_percentage", "hssc_percentage"]:
        val = final_profile.get(key)
        expected_val = EXPECTED.get(key)
        if val is not None:
            match = "OK" if str(val) == str(expected_val) else f"MISMATCH (expected {expected_val!r})"
            print(f"    {key:25s} = {val!r}  [{match}]")
        else:
            print(f"    {key:25s} = {val!r}  [expected {expected_val!r}]")

    # -- Summary --
    stage("SUMMARY")
    missing = []
    for key, expected_val in EXPECTED.items():
        actual = final_profile.get(key)
        if actual is None or str(actual) != str(expected_val):
            missing.append((key, expected_val, actual))

    if missing:
        print(f"  FAIL: {len(missing)} field(s) not carried through pipeline:")
        for key, expected_val, actual in missing:
            print(f"    {key}: expected={expected_val!r}, actual={actual!r}")
    else:
        print("  PASS: All 10 fields carried through the full pipeline.")


if __name__ == "__main__":
    main()
