"""Analyze job descriptions using LLM."""

import json
import re

from langchain_core.prompts import PromptTemplate
from job_agent.state import AnalyzedJob
from job_agent.utils.llm import get_draft_llm

ANALYZE_PROMPT = PromptTemplate.from_template(
    """You are a job analyst. Given a job posting, extract structured information.

Job Title: {title}
Company: {company}
Location: {location}
Description:
{summary}

Extract and return ONLY valid JSON (no markdown, no code fences):
{{
  "requirements": ["req1", "req2", ...],
  "nice_to_haves": ["nice1", "nice2", ...],
  "responsibilities": ["resp1", "resp2", ...],
  "company_description": "brief summary of the company",
  "visa_info": "what the posting says about visa/work permission",
  "has_km_visa": true/false
}}

Set has_km_visa=true if the posting mentions any of:
- KM / kennismigrant / highly skilled migrant
- visa sponsorship / visa support / work visa
- relocation support / sponsorship
- recognised sponsor / erkend referent
"""
)


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown fences and extra text."""
    # Remove markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text)
    # Find first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {}


def analyzer_node(state) -> dict:
    """LangGraph node: parse JD with LLM into structured data."""
    raw_jobs = state.get("raw_jobs", [])
    if not raw_jobs:
        return {"filtered_jobs": []}

    llm = get_draft_llm()
    chain = ANALYZE_PROMPT | llm

    analyzed: list[AnalyzedJob] = []
    for job in raw_jobs:
        print(f"  Analyzing: {job.title} @ {job.company}")
        try:
            result = chain.invoke({
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "summary": job.summary[:3000],
            })
            parsed = _extract_json(result.content)
        except Exception as e:
            print(f"  ✗ Parse error: {e}")
            parsed = {}

        analyzed.append(AnalyzedJob(
            raw=job,
            requirements=parsed.get("requirements", []),
            nice_to_haves=parsed.get("nice_to_haves", []),
            responsibilities=parsed.get("responsibilities", []),
            company_description=parsed.get("company_description", ""),
            visa_info=parsed.get("visa_info", ""),
            has_km_visa=parsed.get("has_km_visa", False),
        ))

    print(f"  ✓ Analyzed {len(analyzed)} jobs")
    return {"filtered_jobs": analyzed}
