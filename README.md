# EduPath AI

An AI-powered university admission assistant for Pakistani students.

EduPath AI combines student document information, structured university/program requirements, rule-based eligibility checking, missing-document detection, deadline information, and grounded AI-generated explanations to guide students through Pakistani university admissions.

## What it does

1. **Upload academic documents** — Students upload FSc / A-Levels transcripts, entry test score cards, CNIC / B-Form, and other documents.
2. **Build a verified profile** — Extracted information is shown for verification and editing.
3. **Select university & program** — Browse a curated dataset of Pakistani universities and programs.
4. **Check eligibility** — Rule-based engine compares the profile against program requirements.
5. **AI advisor** — Grounded explanations and answers based on the student's profile and stored admission data.
6. **Action plan dashboard** — Track progress, current actions, and upcoming steps.

## Tech stack

- **Python** — backend logic
- **Streamlit** — web interface
- **JSON** — initial university data store
- **Git** — version control

## Project structure

```
.
├── Home.py                         # Main Streamlit entry point
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── .gitignore                      # Git ignore rules
├── ui.py                           # Shared Streamlit UI helpers
├── backend/                        # Backend modules
│   ├── __init__.py
│   ├── documents/                  # Validation, OCR, PDF, and field extraction
│   ├── data_loader.py              # Load and query universities.json
│   ├── parser.py                   # Backward-compatible document parsing facade
│   ├── profile.py                  # Student profile management
│   ├── eligibility.py              # Rule-based eligibility engine
│   └── advisor.py                  # Grounded AI advisor responses
├── pages/                          # Streamlit multipage UI
│   ├── 1_Upload_Documents.py
│   ├── 2_Profile.py
│   ├── 3_Select_Program.py
│   ├── 4_Eligibility_Check.py
│   ├── 5_AI_Advisor.py
│   └── 6_Action_Plan.py
├── data/
│   └── universities.json           # Curated Pakistani university data
└── sample_docs/                    # Placeholder for sample documents
```

## Getting started

1. Create a virtual environment (recommended):

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Install Tesseract OCR for PDF/image extraction (Windows):

```bash
winget install --exact --id UB-Mannheim.TesseractOCR
tesseract --version
tesseract --list-langs
```

Ensure `eng` appears in the language list. Put Tesseract on `PATH`, or set `TESSERACT_CMD` to its executable, for example `C:\Program Files\Tesseract-OCR\tesseract.exe`.

4. Run the app:

```bash
streamlit run Home.py
```

## Document extraction

Text files are decoded directly. PDFs with embedded text are read with PyMuPDF; scanned PDF pages and PNG/JPEG uploads use English Tesseract OCR with lightweight grayscale/autocontrast preprocessing. OCR is limited to 10 PDF pages, 5 rendered scan pages, 40 megapixels per image, and 20 seconds per OCR operation. PyMuPDF does not require Poppler.

All extracted values must be verified before building a profile. Password-protected, corrupt, oversized, blank, or partially processed uploads surface a clear validation message and can be completed manually.

For a future Debian-based Streamlit deployment, install `tesseract-ocr` and `tesseract-ocr-eng` through a deployment-specific `packages.txt`; local Windows development does not use that file.

## MVP limitations

- OCR is English-first and can misread low-quality or complex document layouts; always verify extracted details.
- The AI advisor is rule-based and grounded in the stored university data. A real LLM can be plugged in later.
- University data is static JSON and should be verified against official university websites before use.

## Next steps

- Add an LLM for more natural advisor conversations while keeping eligibility logic rule-based.
- Expand the university dataset and add city/program filters.
- Add user accounts and persistent storage.
