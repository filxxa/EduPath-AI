"""AI advisor response generator.

The MVP uses rule-based, grounded explanations rather than a generic LLM so that
advice is always tied to the student's profile and the stored university data.
A real LLM can be swapped in later without changing the interface.
"""
from __future__ import annotations

from typing import Any


COMMON_ADVICE = {
    "nts-nat ie/ics": "Register for the NTS-NAT at https://www.nts.org.pk and select the IE/ICS category relevant to your program.",
    "nts-nat ie": "Register for the NTS-NAT at https://www.nts.org.pk and select the IE category.",
    "nust entry test (net)": "Register for the NET on the official NUST admissions portal and prepare using past papers and the NET syllabus.",
    "lcat / sat": "Register for the LUMS Common Admission Test (LCAT) through the LUMS admissions portal, or submit a valid SAT score if you have one.",
    "ecat (engineering college admission test)": "Register for ECAT through the UET admissions portal. Focus on FSc Math, Physics, Chemistry, and English.",
}


def explain_eligibility(result: dict[str, Any], program: dict[str, Any]) -> str:
    verdict = result["verdict"]
    program_name = f"{program['name']} at {program.get('university_name', 'the selected university')}"

    if verdict == "ELIGIBLE":
        opening = f"Great news — you appear eligible for **{program_name}** based on the information provided."
    elif verdict == "ELIGIBLE - Conditional":
        opening = (
            f"You meet the basic criteria for **{program_name}**, but there are "
            "one or more items you still need to complete before applying."
        )
    else:
        opening = (
            f"Based on the information provided, you do not currently meet the requirements for **{program_name}**. "
            "Here is exactly why, and what you can do about it."
        )

    parts = [opening, ""]

    # Key reasons
    parts.append("**Eligibility breakdown:**")
    for reason in result.get("reasons", []):
        parts.append(f"- {reason}")

    # Missing documents
    missing = result.get("missing_documents", [])
    if missing:
        parts.append("")
        parts.append("**Missing required documents:**")
        for doc in missing:
            parts.append(f"- {doc['name']}")

    # Test advice
    if result.get("test_missing") and result.get("admission_test"):
        test_name = result["admission_test"]
        advice = COMMON_ADVICE.get(test_name.lower(), "Check the university website for registration details.")
        parts.append("")
        parts.append(f"**Next step for admission test ({test_name}):** {advice}")

    # Deadline urgency
    days = result.get("days_remaining")
    if days is not None:
        parts.append("")
        if days < 0:
            parts.append("The deadline has already passed. Consider applying in the next admission cycle.")
        elif days <= 7:
            parts.append(f"Only {days} days left — prioritize completing missing items immediately.")
        elif days <= 30:
            parts.append(f"You have {days} days left. Aim to complete missing documents and tests within the next two weeks.")
        else:
            parts.append(f"You have {days} days until the deadline, which gives you time to prepare properly.")

    # Closing guidance
    if verdict == "NOT ELIGIBLE":
        parts.append("")
        parts.append(
            "If your aggregate or qualification can improve (e.g., retaking exams or adding a recognized equivalence), "
            "recheck eligibility after updating your profile. Otherwise, consider similar programs with lower cutoffs."
        )

    return "\n".join(parts)


def answer_question(question: str, profile: dict[str, Any], result: dict[str, Any], program: dict[str, Any]) -> str:
    """Answer a student question using only grounded data."""
    q = question.lower()

    # Deadline questions
    if any(word in q for word in ["deadline", "last date", "when", "due date"]):
        deadline = result.get("application_deadline")
        days = result.get("days_remaining")
        if deadline:
            return f"The application deadline for **{program['name']}** is **{deadline}** ({days} days from today)."
        return "I don't have a deadline on file for this program. Please check the official university website."

    # Missing documents
    if any(word in q for word in ["missing", "documents", "requirement", "need"]):
        missing = result.get("missing_documents", [])
        if missing:
            doc_names = ", ".join(d["name"] for d in missing)
            return f"You still need: {doc_names}. Upload or verify them in the Profile section."
        return "All required documents appear to be present based on your profile."

    # Eligibility / chances
    if any(word in q for word in ["eligible", "chance", "accept", "admission", "verdict"]):
        return explain_eligibility(result, program)

    # Test registration
    if any(word in q for word in ["test", "register", "nts", "nat", "net", "ecat", "lcat", "sat"]):
        test = result.get("admission_test", "the required admission test")
        advice = COMMON_ADVICE.get(test.lower(), "Visit the official university admissions portal for registration details.")
        return f"For **{test}**: {advice}"

    # Aggregate / cutoff
    if any(word in q for word in ["aggregate", "percentage", "cutoff", "marks", "score"]):
        agg = profile.get("aggregate")
        cutoff = result.get("estimated_cutoff")
        minimum = result.get("minimum_aggregate")
        return (
            f"Your profile aggregate is **{agg}%**. "
            f"The minimum required aggregate is **{minimum}%**, and the estimated cutoff is **{cutoff}%**."
        )

    # Fallback grounded response
    return (
        "I'm here to help with your admission to **" + program.get("name", "this program") + "**. "
        "Ask me about eligibility, deadlines, required documents, or admission tests, and I'll answer based on your verified profile."
    )


def generate_action_plan(result: dict[str, Any], program: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a milestone-style action plan."""
    plan = []

    plan.append({
        "step": 1,
        "title": "Verify Academic Documents",
        "status": "completed" if not result.get("missing_documents") else "current_action",
        "description": "Upload and confirm FSc transcript, Matric certificate, and other academic records.",
    })

    test_name = (
        result.get("admission_test")
        or program.get("requirements", {}).get("admission_test")
        or "Admission Test"
    )

    if result.get("test_missing"):
        plan.append({
            "step": 2,
            "title": f"Register for {test_name}",
            "status": "current_action",
            "description": "Register, prepare, and upload your official score card.",
        })
        plan.append({
            "step": 3,
            "title": "Submit Application",
            "status": "upcoming",
            "description": "Complete the online application before the deadline.",
        })
    else:
        plan.append({
            "step": 2,
            "title": f"{test_name} Score Ready",
            "status": "completed",
            "description": "Your admission test score is recorded.",
        })
        plan.append({
            "step": 3,
            "title": "Submit Application",
            "status": "current_action",
            "description": "Complete the online application before the deadline.",
        })

    plan.append({
        "step": 4,
        "title": "Await Decision",
        "status": "upcoming",
        "description": "Track your application status on the university portal.",
    })

    return plan
