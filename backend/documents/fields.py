"""Structured field extraction from document text."""
from __future__ import annotations

import logging
import re
from typing import Any

from backend.documents.models import ExtractedField

logger = logging.getLogger(__name__)


QUALIFICATION_HINTS: dict[str, str] = {
    "fsc pre-engineering": "FSc Pre-Engineering",
    "pre-engineering": "FSc Pre-Engineering",
    "pre engineering": "FSc Pre-Engineering",
    "fsc pre medical": "FSc Pre-Medical",
    "pre-medical": "FSc Pre-Medical",
    "pre medical": "FSc Pre-Medical",
    "ics": "ICS",
    "fsc": "FSc",
    "a-level": "A-Levels",
    "alevel": "A-Levels",
    "a level": "A-Levels",
    "fa": "FA",
    "dae": "DAE",
}

BOARD_HINTS: dict[str, str] = {
    "fbi": "FBISE Islamabad",
    "fbise": "FBISE Islamabad",
    "fbi se": "FBISE Islamabad",
    "fbise islamabad": "FBISE Islamabad",
    "islamabad": "FBISE Islamabad",
    "federal": "FBISE Islamabad",
    "lahore": "BISE Lahore",
    "karachi": "BISE Karachi",
    "bsek": "BISE Karachi",
    "biek": "BISE Karachi",
    "rawalpindi": "BISE Rawalpindi",
    "peshawar": "BISE Peshawar",
    "multan": "BISE Multan",
    "faisalabad": "BISE Faisalabad",
    "sargodha": "BISE Sargodha",
    "gujranwala": "BISE Gujranwala",
    "bahawalpur": "BISE Bahawalpur",
    "sahiwal": "BISE Sahiwal",
    "dera ghazi khan": "BISE Dera Ghazi Khan",
    "dgk": "BISE Dera Ghazi Khan",
    "mirpurkhas": "BISE Mirpurkhas",
    "mirpur khas": "BISE Mirpurkhas",
    "hyderabad": "BISE Hyderabad",
    "sukkur": "BISE Sukkur",
    "larkana": "BISE Larkana",
    "abbottabad": "BISE Abbottabad",
    "bannu": "BISE Bannu",
    "kohat": "BISE Kohat",
    "mirpur": "BIM Kashmir",
    "mirpur kashmir": "BIM Kashmir",
    "ajk": "BIM Kashmir",
    "aga khan": "Aga Khan University",
    "aku": "Aga Khan University",
}



def _clean_text(text: str) -> str:
    """Normalize text for matching."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def _find_first(patterns: list[str], text: str) -> re.Match | None:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m
    return None


_NAME_LABEL = re.compile(
    r"^\s*(?:name\s+of\s+candidate|student\s+name|candidate\s+name|name)\s*[:\-]?\s*(.*?)\s*[;:|/\\]*\s*$",
    re.IGNORECASE,
)
_NAME_METADATA_WORDS = {
    "board", "candidate", "certificate", "class", "cnic", "department", "father",
    "form", "guardian", "marks", "name", "number", "of", "qualification", "result",
    "roll", "student", "subject", "total",
}


def _normalize_name(candidate: str) -> str | None:
    """Validate and normalize a likely student name without guessing from metadata."""
    candidate = candidate.strip(" \t:-;|/\\")
    if not candidate or "\n" in candidate:
        return None
    tokens = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)?", candidate)
    if not 2 <= len(tokens) <= 4:
        return None
    alpha_only = " ".join(tokens)
    if alpha_only.lower() != re.sub(r"\s+", " ", candidate).lower().strip(" \t:-;|/\\"):
        cleaned_candidate = re.sub(r"[^A-Za-z\s'\-]", "", candidate)
        if alpha_only.lower() != re.sub(r"\s+", " ", cleaned_candidate).lower().strip():
            return None
    if any(token.lower() in _NAME_METADATA_WORDS for token in tokens):
        return None
    if candidate.isupper() or candidate.islower():
        return " ".join(tokens).title()
    return " ".join(tokens)


def extract_name(text: str) -> str | None:
    """Extract a validated student name from labeled lines or an honorific fallback."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = _NAME_LABEL.match(line)
        if not match:
            continue
        candidate = match.group(1).strip()
        if not candidate:
            candidate = next((value.strip() for value in lines[index + 1 :] if value.strip()), "")
        name = _normalize_name(candidate)
        if name:
            return name

    for line in lines:
        match = re.search(r"\b(?:mr|ms|mrs)\.?\s+(.+)$", line, re.IGNORECASE)
        if match:
            name = _normalize_name(match.group(1))
            if name:
                return name

    header_keywords = re.compile(
        r"\b(?:roll\s*(?:no|number)?|seat\s*(?:no|number)?|registration|enrollment|adm(?:ission)?(?:\s*no)?)\b",
        re.IGNORECASE,
    )
    title_case_pattern = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b")
    all_caps_pattern = re.compile(r"\b([A-Z]{2,}(?:\s+[A-Z]{2,}){1,3})\b")
    for index, line in enumerate(lines):
        if header_keywords.search(line):
            for nearby_line in lines[max(0, index - 1) : index + 3]:
                candidates = title_case_pattern.findall(nearby_line)
                for candidate in candidates:
                    name = _normalize_name(candidate)
                    if name:
                        return name
                all_caps_candidates = all_caps_pattern.findall(nearby_line)
                for candidate in all_caps_candidates:
                    name = _normalize_name(candidate.title())
                    if name:
                        return name
    return None


_FATHER_LABEL = re.compile(
    r"^\s*father[''`]?\s*s?\s*name\s*[:\-]?\s*(.*?)\s*[;:|/\\]*\s*$",
    re.IGNORECASE,
)


def extract_father_name(text: str) -> str | None:
    """Extract father's name from labeled lines, tolerating OCR artifacts."""
    for line in text.splitlines():
        match = _FATHER_LABEL.match(line)
        if not match:
            continue
        candidate = match.group(1).strip()
        if not candidate:
            continue
        name = _normalize_name(candidate)
        if name:
            return name
    return None


_NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
}


def _number_from_words(text: str) -> int | None:
    """Convert English number words to an integer (e.g. 'SEVEN HUNDRED AND SIXTY ONE' → 761)."""
    connectors = {"and", "only", "exactly"}
    words = [w for w in re.findall(r"[A-Za-z]+", text.lower()) if w not in connectors]
    if not words or not all(w in _NUMBER_WORDS for w in words):
        return None
    total = 0
    current = 0
    for w in words:
        val = _NUMBER_WORDS[w]
        if val == 100:
            current = current * val if current else val
        elif val == 1000:
            total = (total + current) * val if current else total * val
            current = 0
        else:
            current += val
    return total + current


def extract_qualification(text: str) -> str | None:
    """Map extracted qualification text to a standard label."""
    cleaned = _clean_text(text)
    for hint, value in QUALIFICATION_HINTS.items():
        if re.search(rf"\b{re.escape(_clean_text(hint))}\b", cleaned):
            return value
    return None


_OCR_EDU_TYPOS = re.compile(r"\b(?:h?ducat(?:ion)?|educ(?:at(?:ion)?)?|eduction)\b", re.IGNORECASE)


def extract_board(text: str) -> str | None:
    """Map extracted board text to a standard label.

    Tolerates OCR misreads of "Education" (e.g. "Hducat", "Educat") by
    normalizing them before matching. Falls back to city-name extraction
    from board-like lines when no hint matches directly.
    """
    cleaned = _clean_text(text)
    normalized = _OCR_EDU_TYPOS.sub("education", cleaned)
    for hint, value in BOARD_HINTS.items():
        if hint in normalized:
            return value

    for line in text.splitlines():
        if re.search(r"\bboard\b", line, re.IGNORECASE):
            line_clean = _clean_text(line)
            line_norm = _OCR_EDU_TYPOS.sub("education", line_clean)
            for hint, value in BOARD_HINTS.items():
                if hint in line_norm:
                    return value
    return None


def _as_percentage(value: str) -> float | None:
    """Return a numeric percentage only when it is within the valid range."""
    number = float(value)
    return number if 0 <= number <= 100 else None


def _ratio_percentage(obtained: str, total: str) -> float | None:
    """Calculate a percentage only for a sensible obtained/total ratio."""
    obtained_value = float(obtained)
    total_value = float(total)
    if total_value <= 0 or obtained_value < 0 or obtained_value > total_value:
        return None
    percentage = obtained_value / total_value * 100
    return round(percentage, 2) if 0 <= percentage <= 100 else None


def extract_aggregate(text: str) -> float | None:
    """Extract a defensible academic percentage without treating IDs as marks."""
    labeled_patterns = [
        r"\baggregate\b(?:\s+(?:marks?|score))?\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*%?",
        r"\b(?:overall\s+)?percentage\b(?:\s+(?:marks?|score))?\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*%?",
    ]
    for pattern in labeled_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            percentage = _as_percentage(match.group(1))
            if percentage is not None:
                return percentage

    ratio_patterns = [
        r"\b(?:marks?\s+)?obtained\b\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*(?:out\s+of|/)\s*(\d+(?:\.\d+)?)",
        r"\b(?:marks?\s+)?obtained\b\s*[:=\-]?\s*(\d+(?:\.\d+)?)[\s\S]{0,80}?\btotal\s+(?:marks?)?\b\s*[:=\-]?\s*(\d+(?:\.\d+)?)",
        r"\bobtained\s+marks?\b\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*(?:out\s+of|/)\s*\btotal\s+marks?\b\s*[:=\-]?\s*(\d+(?:\.\d+)?)",
        r"\bobtained\b\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s+\btotal\b\s*[:=\-]?\s*(\d+(?:\.\d+)?)",
    ]
    for pattern in ratio_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            percentage = _ratio_percentage(match.group(1), match.group(2))
            if percentage is not None:
                return percentage

    for match in re.finditer(r"\btotal\s+(?:marks?\b\s*[:=\-]?\s*)?(\d{3,4})\s+(\d{3,4})", text, re.IGNORECASE):
        percentage = _ratio_percentage(match.group(2), match.group(1))
        if percentage is not None:
            return percentage

    for match in re.finditer(r"\b(\d+(?:\.\d+)?)\s*%", text):
        percentage = _as_percentage(match.group(1))
        if percentage is not None:
            return percentage

    words_match = re.search(
        r"\bobtained\s+marks?\s*\(?\s*in\s+words\s*\)?\s*[;:]*\s*(.+)",
        text,
        re.IGNORECASE,
    )
    if words_match:
        obtained = _number_from_words(words_match.group(1))
        if obtained is not None:
            total_match = re.search(r"\btotal\s+(?:marks?\b\s*[:=\-]?\s*)?(\d{3,4})", text, re.IGNORECASE)
            if total_match:
                percentage = _ratio_percentage(str(obtained), total_match.group(1))
                if percentage is not None:
                    return percentage

    for line in text.splitlines():
        numbers = re.findall(r"\b(\d{2,4})\b", line)
        if len(numbers) < 2:
            continue
        nums = [int(n) for n in numbers if 100 <= int(n) <= 1500]
        if len(nums) < 2:
            continue
        best: float | None = None
        for i, a in enumerate(nums):
            for b in nums[i + 1 :]:
                total_val = max(a, b)
                obtained_val = min(a, b)
                if 500 <= total_val <= 1100 and obtained_val < total_val:
                    pct = _ratio_percentage(str(obtained_val), str(total_val))
                    if pct is not None and (best is None or abs(pct - 50) < abs(best - 50)):
                        best = pct
        if best is not None:
            return best
    return None


def extract_test_score(text: str) -> dict[str, str | None] | None:
    """Extract a test name, score, total score, date, and roll number if present."""
    test_patterns = [
        r"\bmuet\b(?:\s+computer[\s-]*based[\s-]*pre[\s-]*admission[\s-]*test)?",
        r"\bfast[\s-]*(?:nuces|university)[\s-]*(?:entry[\s-]*)?test\b",
        r"\bnts[\s-]*nat(?:[\s-]*(?:ie|ics|icom|igs))?\b",
        r"\bnat[\s-]*(?:ie|ics|icom|igs)\b",
        r"\b(?:nts|nat)\b\s*(?:ie)?\s*(?:ics)?",
        r"\bnust\s*entry\s*test\b",
        r"\bnet\b(?:\s+(?:engineering|business|architecture|natural\s+sciences|applied\s+sciences))?",
        r"\becat\b(?:\s*\d{4})?",
        r"\bsat\b",
        r"\bact\b",
        r"\blcat\b",
    ]
    found_test: str | None = None
    cleaned = _clean_text(text)
    for pat in test_patterns:
        m = re.search(pat, cleaned, re.IGNORECASE)
        if m:
            found_test = m.group(0).upper().strip()
            break

    if not found_test:
        return None

    score_patterns = [
        r"score[\s:]*(\d+(?:\.\d+)?)",
        r"marks[\s:]*(\d+(?:\.\d+)?)",
        r"percent(?:ile)?[\s:]*(\d+(?:\.\d+)?)",
    ]
    score_match = _find_first(score_patterns, text)
    score = score_match.group(1).strip() if score_match else ""

    roll_patterns = [
        r"roll\s*(?:no\.?|number)[\s:]*([\w\-]+)",
        r"seat\s*(?:no\.?|number)[\s:]*([\w\-]+)",
        r"registration\s*(?:no\.?|number)[\s:]*([\w\-]+)",
    ]
    roll_match = _find_first(roll_patterns, text)
    roll_number = roll_match.group(1).strip() if roll_match else None

    total_patterns = [
        r"(?:total|out\s+of|max(?:imum)?)\s*(?:score|marks)?[\s:]*(\d+)",
        r"(\d+)\s*/\s*(\d+)",
    ]
    total_score: str | None = None
    total_match = _find_first(total_patterns, text)
    if total_match:
        groups = total_match.groups()
        if len(groups) == 2 and groups[1]:
            total_score = groups[1].strip()
        else:
            total_score = groups[0].strip()

    date_patterns = [
        r"(?:test\s+date|date\s+of\s+(?:test|exam))[\s:]*(\d{1,2}[\s/-]\d{1,2}[\s/-]\d{2,4})",
        r"(?:test\s+date|date\s+of\s+(?:test|exam))[\s:]*((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{4})",
    ]
    test_date: str | None = None
    date_match = _find_first(date_patterns, text)
    if date_match:
        test_date = date_match.group(1).strip()

    if not score and not roll_number:
        return None

    result: dict[str, str | None] = {
        "test": found_test,
        "score": score or None,
        "total_score": total_score,
        "test_date": test_date,
        "roll_number": roll_number,
    }
    return result


_ROLL_NUMBER_LABEL = re.compile(
    r"\b(?:roll\s*(?:no\.?|number)|seat\s*(?:no\.?|number)|registration\s*(?:no\.?|number))\b",
    re.IGNORECASE,
)


def extract_roll_number(text: str) -> str | None:
    """Extract a roll / seat / registration number from labeled lines.

    Pakistani marksheets typically have patterns like:
      ROLL NUMBER 123456
      ROLL NO. 78901
      SEAT NUMBER 45678
    The value is the first sequence of digits (possibly with hyphens) after the label.
    """
    for line in text.splitlines():
        if not _ROLL_NUMBER_LABEL.search(line):
            continue
        after_label = _ROLL_NUMBER_LABEL.split(line, maxsplit=1)[-1]
        digits_match = re.search(r"[\d][\d\s\-/]{2,}", after_label)
        if digits_match:
            value = re.sub(r"[\s\-/]+", "", digits_match.group(0)).strip()
            if 3 <= len(value) <= 15:
                return value
    return None


def extract_obtained_marks(text: str) -> int | None:
    """Extract total obtained marks from labeled lines.

    Handles patterns like:
      TOTAL OBTAINED MARKS: 535
      MARKS OBTAINED: 535
      TOTAL OBTAINED: 535
    """
    patterns = [
        r"\btotal\s+obtained\s+marks?\s*[:=\-]?\s*(\d+)",
        r"\bmarks?\s+obtained\s*[:=\-]?\s*(\d+)",
        r"\btotal\s+obtained\s*[:=\-]?\s*(\d+)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            value = int(match.group(1))
            if 0 < value <= 1500:
                return value
    return None


def extract_total_marks(text: str) -> int | None:
    """Extract total marks from labeled lines.

    Handles patterns like:
      TOTAL MARKS: 700
      TOTAL: 700
    Must avoid matching 'TOTAL OBTAINED MARKS' — that is obtained, not total.
    """
    for line in text.splitlines():
        if re.search(r"\bobtained\b", line, re.IGNORECASE):
            continue
        match = re.search(r"\btotal\s+marks?\s*[:=\-]?\s*(\d+)", line, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            if 0 < value <= 1500:
                return value
    for match in re.finditer(r"\btotal\s*[:=\-]\s*(\d{3,4})\b", text, re.IGNORECASE):
        value = int(match.group(1))
        if 0 < value <= 1500:
            preceding = text[max(0, match.start() - 20):match.start()].lower()
            if "obtained" not in preceding:
                return value
    return None


_OCR_NUMERIC_CORRECTIONS = str.maketrans({
    "O": "0", "o": "0", "D": "0",
    "I": "1", "l": "1",
    "S": "5", "s": "5",
    "B": "8",
    "G": "6", "g": "9",
    "Z": "2", "z": "2",
})


def _correct_ocr_numeric(value: str) -> str:
    """Fix common OCR misreads in numeric strings (O→0, I→1, S→5, etc.)."""
    if not value or not any(c.isdigit() for c in value):
        return value
    return value.translate(_OCR_NUMERIC_CORRECTIONS)


_KV_FIELD_MAP = {
    "name": ["name", "student name", "candidate name", "name of candidate"],
    "father_name": ["father", "father's name", "fathers name", "father name", "guardian"],
    "board": ["board", "university board", "examining body"],
    "qualification": ["qualification", "program", "course", "class"],
    "roll_number": ["roll no", "roll number", "seat no", "seat number", "registration"],
}


def _guess_key_value_fields(text: str) -> dict[str, str]:
    """Fallback: scan for key-value patterns line-by-line.

    Handles both colon-separated ("Name: Ali") and space-separated
    ("NAME OF CANDIDATE ALI HASSAN") layouts common in Pakistani marksheets.
    """
    results: dict[str, str] = {}
    kv_pattern = re.compile(r"^\s*([^:\-\n]{2,40})\s*[:\-]\s*(.+?)\s*$")
    space_kv_pattern = re.compile(
        r"^\s*(name\s+of\s+candidate|father.s?\s*name|roll\s*(?:no\.?|number)|"
        r"seat\s*(?:no\.?|number)|registration\s*(?:no\.?|number))\s+(.+?)\s*$",
        re.IGNORECASE,
    )

    for line in text.splitlines():
        match = kv_pattern.match(line) or space_kv_pattern.match(line)
        if not match:
            continue
        key_raw = match.group(1).strip().lower()
        value_raw = match.group(2).strip()

        for field_name, key_variants in _KV_FIELD_MAP.items():
            if field_name in results:
                continue
            for variant in key_variants:
                if variant in key_raw:
                    results[field_name] = value_raw
                    break
    return results


def extract_fields(filename: str, text: str, canonical_category: str | None) -> list[ExtractedField]:
    """Extract structured fields from document text.

    When ``canonical_category`` identifies the document as an intermediate
    transcript or matric certificate, the percentage is emitted under the
    split field name (``hssc_percentage`` / ``ssc_percentage``) so the
    student profile preserves Pakistani-style academic granularity. The
    legacy ``aggregate`` field is still emitted as a backwards-compat
    fallback so consumers that have not yet migrated continue to work.

    Confidence is left as None for rule-based extractions because a regex
    cannot produce a calibrated confidence score. The field is still present
    so future OCR/ML stages can populate it without changing the schema.
    """
    fields: list[ExtractedField] = []
    source = filename

    name = extract_name(text)
    if name:
        fields.append(
            ExtractedField(
                field="name",
                value=name,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    father_name = extract_father_name(text)
    if father_name:
        fields.append(
            ExtractedField(
                field="father_name",
                value=father_name,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    qualification = extract_qualification(text)
    if qualification:
        fields.append(
            ExtractedField(
                field="qualification",
                value=qualification,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    board = extract_board(text)
    if board:
        fields.append(
            ExtractedField(
                field="board",
                value=board,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    aggregate = extract_aggregate(text)
    if aggregate is not None:
        if canonical_category == "intermediate_transcript":
            fields.append(
                ExtractedField(
                    field="hssc_percentage",
                    value=aggregate,
                    confidence=None,
                    source_document=source,
                    extraction_method="regex",
                )
            )
            group = _extract_group(text)
            if group:
                fields.append(
                    ExtractedField(
                        field="hssc_group",
                        value=group,
                        confidence=None,
                        source_document=source,
                        extraction_method="regex",
                    )
                )
        elif canonical_category == "matric_certificate":
            fields.append(
                ExtractedField(
                    field="ssc_percentage",
                    value=aggregate,
                    confidence=None,
                    source_document=source,
                    extraction_method="regex",
                )
            )

        # Legacy aggregate is always emitted as a backwards-compat fallback.
        fields.append(
            ExtractedField(
                field="aggregate",
                value=aggregate,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    test_score = extract_test_score(text)
    if test_score:
        fields.append(
            ExtractedField(
                field="test_score",
                value=test_score,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    roll_number = extract_roll_number(text)
    if roll_number:
        fields.append(
            ExtractedField(
                field="roll_number",
                value=roll_number,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    obtained_marks = extract_obtained_marks(text)
    if obtained_marks is not None:
        fields.append(
            ExtractedField(
                field="obtained_marks",
                value=obtained_marks,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    total_marks = extract_total_marks(text)
    if total_marks is not None:
        fields.append(
            ExtractedField(
                field="total_marks",
                value=total_marks,
                confidence=None,
                source_document=source,
                extraction_method="regex",
            )
        )

    extracted_keys = {f.field for f in fields}
    fallback_candidates = {"name", "father_name", "board", "qualification", "roll_number"}
    if fallback_candidates & extracted_keys != fallback_candidates:
        guessed = _guess_key_value_fields(text)
        for field_name, raw_value in guessed.items():
            if field_name in extracted_keys:
                continue
            normalized = _normalize_fallback_value(field_name, raw_value)
            if normalized is not None:
                fields.append(
                    ExtractedField(
                        field=field_name,
                        value=normalized,
                        confidence=None,
                        source_document=source,
                        extraction_method="kv_fallback",
                    )
                )
                extracted_keys.add(field_name)

    fields = _validate_percentage_from_marks(fields)

    logger.info(
        "Field extraction: file=%s text_len=%d fields_extracted=%d fields=%s",
        filename,
        len(text),
        len(fields),
        {f.field: f.value for f in fields},
    )

    return fields


def _normalize_fallback_value(field_name: str, raw_value: str) -> Any:
    """Run a fallback key-value value through the same validator as primary extraction."""
    if field_name == "name":
        return _normalize_name(raw_value)
    if field_name == "father_name":
        return _normalize_name(raw_value)
    if field_name == "board":
        return extract_board(raw_value)
    if field_name == "qualification":
        return extract_qualification(raw_value)
    if field_name == "roll_number":
        corrected = _correct_ocr_numeric(raw_value)
        digits = re.sub(r"[^\d]", "", corrected)
        return digits if 3 <= len(digits) <= 15 else None
    return raw_value if raw_value else None


def _validate_percentage_from_marks(fields: list[ExtractedField]) -> list[ExtractedField]:
    """Recompute percentage from total_marks/obtained_marks when OCR digit is suspect.

    OCR frequently misreads digits (e.g. "77" as "17"). When we have both the
    raw marks and an OCR-extracted percentage, we can verify the percentage by
    recomputing it. If the difference exceeds a threshold, we trust the
    arithmetic over the OCR.
    """
    field_map = {f.field: f for f in fields}
    total = field_map.get("total_marks")
    obtained = field_map.get("obtained_marks")
    pct_field = field_map.get("hssc_percentage") or field_map.get("ssc_percentage") or field_map.get("aggregate")

    if total is None or obtained is None or pct_field is None:
        return fields

    total_val = total.value if isinstance(total.value, (int, float)) else None
    obtained_val = obtained.value if isinstance(obtained.value, (int, float)) else None
    pct_val = pct_field.value if isinstance(pct_field.value, (int, float)) else None

    if total_val is None or obtained_val is None or pct_val is None:
        return fields
    if total_val <= 0:
        return fields

    computed = round((obtained_val / total_val) * 100, 2)
    if abs(computed - pct_val) > 5.0:
        logger.info(
            "Percentage OCR mismatch: ocr=%.2f computed=%.2f (obtained=%d/total=%d) -- using computed",
            pct_val, computed, obtained_val, total_val,
        )
        corrected_fields = []
        for f in fields:
            if f.field == pct_field.field:
                corrected_fields.append(ExtractedField(
                    field=f.field,
                    value=computed,
                    confidence=None,
                    source_document=f.source_document,
                    extraction_method="computed_from_marks",
                ))
            elif f.field == "aggregate":
                corrected_fields.append(ExtractedField(
                    field=f.field,
                    value=computed,
                    confidence=None,
                    source_document=f.source_document,
                    extraction_method="computed_from_marks",
                ))
            else:
                corrected_fields.append(f)
        return corrected_fields

    return fields


def _extract_group(text: str) -> str | None:
    """Detect the HSSC group from transcript text."""
    cleaned = _clean_text(text)
    group_map = [
        ("pre engineering", "Pre-Engineering"),
        ("pre-engineering", "Pre-Engineering"),
        ("pre medical", "Pre-Medical"),
        ("pre-medical", "Pre-Medical"),
        ("general science", "General Science"),
        ("humanities", "Humanities"),
        ("commerce", "Commerce"),
    ]
    for hint, value in group_map:
        if hint in cleaned:
            return value
    return None
