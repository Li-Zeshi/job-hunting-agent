from typing import Optional, Literal
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class RawJob(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    summary: str = ""
    url: str = ""
    source: str = "indeed"


class AnalyzedJob(BaseModel):
    raw: RawJob = Field(default_factory=RawJob)
    requirements: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    company_description: str = ""
    visa_info: str = ""
    has_km_visa: bool = False
    match_score: int = 0
    match_reasoning: str = ""


class BQStory(BaseModel):
    title: str = ""
    content: str = ""
    competencies: list[str] = Field(default_factory=list)
    relevance_score: float = 0.0


class ApplicationRecord(BaseModel):
    job: AnalyzedJob = Field(default_factory=AnalyzedJob)
    tailored_resume: str = ""
    cover_letter: str = ""
    matched_stories: list[BQStory] = Field(default_factory=list)
    review_status: str = "pending"
    review_feedback: str = ""
    timestamp: str = ""


class JobAgentState(TypedDict):
    # search params
    search_keywords: str
    search_location: str

    # job pipeline
    raw_jobs: list[RawJob]
    filtered_jobs: list[AnalyzedJob]
    skipped_jobs: list[AnalyzedJob]

    # current job being processed
    current_job_index: int
    current_job: Optional[AnalyzedJob]

    # resume
    resume_text: str
    tailored_resume: str

    # bq stories
    bq_stories: list[BQStory]
    matched_stories: list[BQStory]

    # cover letter
    cover_letter: str

    # review
    review_status: Optional[Literal["approved", "rejected", "modified"]]
    review_feedback: str

    # history
    today_applications: list[ApplicationRecord]
