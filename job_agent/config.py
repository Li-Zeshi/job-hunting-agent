from pathlib import Path

# ── Paths ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "job_agent" / "data"
BQ_STORIES_DIR = DATA_DIR / "bq_stories"
RESUME_PATH = DATA_DIR / "resume.md"
CHROMA_DB_DIR = DATA_DIR / "chroma_db"
APPLICATIONS_PATH = DATA_DIR / "applications.json"
JOBS_CACHE_PATH = DATA_DIR / "jobs_cache.json"

# ── Job search ──
DEFAULT_LOCATION = "Netherlands"
MATCH_THRESHOLD = 40  # minimum match score 0-100 (lower for small models)
MAX_JOBS_PER_RUN = 10  # max jobs to process per run

# ── KM visa keywords (Dutch highly skilled migrant) ──
KM_VISA_KEYWORDS = [
    "km visa", "kennismigrant", "highly skilled migrant",
    "visa sponsorship", "visa sponsoring", "work visa",
    "work permit", "relocation support", "relocation package",
    "visa support", "sponsorship", "sponsorvisum", "visum",
    "ind sponsorship", "recognised sponsor", "erkend referent",
    "visa sponsorship available", "would sponsor",
    "sponsor a visa", "sponsorship is available",
]

# ── IND recognised sponsors (partial list — helps detect visa sponsorship) ──
KNOWN_SPONSORS = [
    "booking.com", "uber", "netflix", "spotify", "mollie", "adyen",
    "ing", "abn amro", "rabobank", "shell", "philips", "asml",
    "bolt", "messagebird", "channable", "elastic", "databricks",
    "picnic", "takeaway", "just eat takeaway", "bunq", "finan",
    "ing bank", "abn amro bank", "rabobank nederland",
]

# ── LLM ──
LLM_PROVIDER = "ollama"  # "ollama" | "openai"
OLLAMA_MODEL = "gemma3:270m"  # small model; for better quality try: llama3.2:3b or qwen2.5:7b
OPENAI_MODEL = "gpt-4o"
DRAFT_MODEL = "ollama"
FINAL_MODEL = "ollama"
