"""Generate a compelling cover letter / motivation letter."""

from langchain_core.prompts import PromptTemplate
from job_agent.utils.llm import get_final_llm

COVER_LETTER_PROMPT = PromptTemplate.from_template(
    """You are a professional cover letter writer. Write a compelling, passionate motivation letter.

## Job:
- Title: {job_title}
- Company: {company}
- Company description: {company_desc}

## Key Requirements:
{requirements}

## My Resume (tailored):
{tailored_resume}

## My BQ Stories (relevant personal experiences):
{bq_stories}

Write a motivation letter that:
1. Opens with genuine enthusiasm for the company and role
2. Connects the candidate's experience (from resume) to what the role needs
3. Weaves in 1-2 of the BQ stories as concrete examples of relevant skills
4. Shows understanding of the company's mission/impact
5. Is professional but warm — NOT generic or template-like
6. Closes with a confident call to action
7. **Keep it to 3-4 paragraphs max, under 350 words**

Return ONLY the letter text (no subject line, no JSON).
"""
)


def writer_node(state) -> dict:
    """LangGraph node: generate cover letter."""
    current_job = state.get("current_job")
    resume = state.get("tailored_resume", "")
    stories = state.get("matched_stories", [])

    if not current_job or not resume:
        return {"cover_letter": ""}

    llm = get_final_llm()
    chain = COVER_LETTER_PROMPT | llm

    reqs = "\n".join(f"- {r}" for r in current_job.requirements[:8]) or "Not specified"
    story_text = "\n\n".join(
        f"Story: {s.title}\n{s.content}" for s in stories
    ) or "No specific stories provided."

    print(f"  Writing cover letter for {current_job.raw.title}...")
    try:
        result = chain.invoke({
            "job_title": current_job.raw.title,
            "company": current_job.raw.company,
            "company_desc": current_job.company_description or "Not specified",
            "requirements": reqs,
            "tailored_resume": resume[:2000],
            "bq_stories": story_text,
        })
        letter = result.content.strip()
    except Exception as e:
        print(f"  ✗ Cover letter error: {e}")
        letter = ""

    print(f"  ✓ Cover letter generated ({len(letter.split())} words)")
    return {"cover_letter": letter}
