"""Match analyzed jobs against resume, score and filter by visa."""

import json
import re

from langchain_core.prompts import PromptTemplate
from job_agent import config as cfg
from job_agent.state import AnalyzedJob
from job_agent.utils.llm import get_draft_llm

MATCH_PROMPT = PromptTemplate.from_template(
    """You are a hiring matchmaker. Score how well the candidate's resume fits a job.

## Resume:
{resume}

## Job Requirements:
{requirements}

## Nice-to-haves:
{nice_to_haves}

## Responsibilities:
{responsibilities}

Return ONLY valid JSON:
{{
  "match_score": <0-100 integer>,
  "reasoning": "<1-2 sentence explanation>"
}}

Scoring rubric:
- 80-100: Perfect match (most requirements met, strong alignment)
- 60-79: Good match (key requirements met, some gaps)
- 40-59: Moderate match (some overlap, significant gaps)
- 0-39: Poor match (little alignment)
"""
)


def _check_visa(job: AnalyzedJob) -> bool:
    if job.has_km_visa:
        return True
    text = (
        job.raw.summary + " " +
        job.visa_info + " " +
        job.raw.title + " " +
        job.company_description
    ).lower()
    return any(kw in text for kw in cfg.KM_VISA_KEYWORDS)


def _check_known_sponsor(job: AnalyzedJob) -> bool:
    company = job.raw.company.lower().strip()
    return any(sponsor in company for sponsor in cfg.KNOWN_SPONSORS)


def _keyword_score(resume: str, job: AnalyzedJob) -> int:
    """Fallback scoring: keyword overlap between resume and JD."""
    resume_words = set(re.findall(r"\w+", resume.lower()))
    if not resume_words:
        return 0

    jd_text = " ".join(job.requirements) + " " + " ".join(job.responsibilities)
    jd_words = set(re.findall(r"\w+", jd_text.lower()))

    if not jd_words:
        return 50  # No requirements to match — assume moderate fit

    overlap = resume_words & jd_words
    score = int(len(overlap) / len(jd_words) * 100)
    return min(score, 100)


def _extract_llm_score(result_content: str) -> tuple[int, str]:
    """Try to extract JSON score from LLM output."""
    json_match = re.search(r"\{.*\}", result_content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            return int(parsed.get("match_score", 0)), parsed.get("reasoning", "")
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return 0, ""


def matcher_node(state) -> dict:
    """LangGraph node: score jobs and filter by visa + match threshold."""
    jobs = state.get("filtered_jobs", [])
    resume = state.get("resume_text", "")
    if not jobs:
        return {"filtered_jobs": [], "skipped_jobs": []}

    llm = get_draft_llm()
    chain = MATCH_PROMPT | llm

    good_jobs: list[AnalyzedJob] = []
    skipped: list[AnalyzedJob] = []

    for job in jobs:
        # 1) Visa check first
        has_visa = _check_visa(job) or _check_known_sponsor(job)
        if not has_visa:
            print(f"  ⏭ {job.raw.title} @ {job.raw.company} — no KM visa detected")
            job.match_score = 0
            job.match_reasoning = "No KM visa detected"
            skipped.append(job)
            continue

        # 2) LLM scoring
        reqs = "\n".join(f"- {r}" for r in job.requirements[:10]) or "Not specified"
        nice = "\n".join(f"- {n}" for n in job.nice_to_haves[:5]) or "Not specified"
        resp = "\n".join(f"- {r}" for r in job.responsibilities[:10]) or "Not specified"

        score, reasoning = 0, ""
        try:
            result = chain.invoke({
                "resume": resume[:3000],
                "requirements": reqs,
                "nice_to_haves": nice,
                "responsibilities": resp,
            })
            score, reasoning = _extract_llm_score(result.content)
        except Exception as e:
            print(f"  ⚠ LLM match error: {e}")

        # 3) Fallback: keyword score if LLM failed
        if score == 0:
            score = _keyword_score(resume, job)
            reasoning = f"Keyword-based score (LLM produced invalid JSON)"
            print(f"  ⚠ Using keyword fallback score: {score}")

        job.match_score = score
        job.match_reasoning = reasoning

        if score >= cfg.MATCH_THRESHOLD:
            print(f"  ✅ {job.raw.title} @ {job.raw.company} — score={score}, visa=✓")
            good_jobs.append(job)
        else:
            print(f"  ⏭ {job.raw.title} @ {job.raw.company} — score={score} < {cfg.MATCH_THRESHOLD}")
            skipped.append(job)

    print(f"  ✓ {len(good_jobs)} matched, {len(skipped)} skipped")
    return {"filtered_jobs": good_jobs, "skipped_jobs": skipped, "current_job_index": 0}
