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
├── app.py                          # Main Streamlit entry point
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── .gitignore                      # Git ignore rules
├── ui.py                           # Shared Streamlit UI helpers
├── backend/                        # Backend modules
│   ├── __init__.py
│   ├── data_loader.py              # Load and query universities.json
│   ├── parser.py                   # Document parsing helpers
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

3. Run the app:

```bash
streamlit run app.py
```

## MVP limitations

- Document parsing is simulated. Text files (`.txt`, `.md`) are parsed using simple pattern matching. PDFs and images show a placeholder and require manual verification.
- The AI advisor is rule-based and grounded in the stored university data. A real LLM can be plugged in later.
- University data is static JSON and should be verified against official university websites before use.

## Next steps

- Integrate OCR or document AI for real PDF/image parsing.
- Add an LLM for more natural advisor conversations while keeping eligibility logic rule-based.
- Expand the university dataset and add city/program filters.
- Add user accounts and persistent storage.
