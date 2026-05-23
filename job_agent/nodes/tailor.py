"""Tailor resume based on job description."""

from langchain_core.prompts import PromptTemplate
from job_agent.utils.llm import get_final_llm

TAILOR_PROMPT = PromptTemplate.from_template(
    """You are a professional resume writer. Tailor the candidate's resume for a specific job.

## Original Resume:
{resume}

## Job Title: {job_title}
## Company: {company}

## Key Requirements:
{requirements}

## Key Responsibilities:
{responsibilities}

Rewrite the resume to:
1. Reorder skills to put the most relevant ones first
2. Add relevant keywords from the job description naturally
3. Rewrite bullet points to emphasize experience matching this role
4. Keep it truthful — do not invent experience
5. Keep the same overall structure but make it ATS-friendly

Return the FULL tailored resume as plain text (no JSON wrapping).
"""
)


def tailor_node(state) -> dict:
    """LangGraph node: tailor resume for current job."""
    current_job = state.get("current_job")
    resume = state.get("resume_text", "")
    if not current_job or not resume:
        return {"tailored_resume": resume}

    llm = get_final_llm()
    chain = TAILOR_PROMPT | llm

    reqs = "\n".join(f"- {r}" for r in current_job.requirements[:10]) or "Not specified"
    resp = "\n".join(f"- {r}" for r in current_job.responsibilities[:8]) or "Not specified"

    print(f"  Tailoring resume for {current_job.raw.title}...")
    try:
        result = chain.invoke({
            "resume": resume,
            "job_title": current_job.raw.title,
            "company": current_job.raw.company,
            "requirements": reqs,
            "responsibilities": resp,
        })
        tailored = result.content
    except Exception as e:
        print(f"  ✗ Tailor error: {e}")
        tailored = resume

    return {"tailored_resume": tailored}
