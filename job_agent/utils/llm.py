from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from job_agent import config as cfg

_llm_cache: dict = {}


def get_llm(provider: str | None = None, temperature: float = 0) -> ChatOpenAI | ChatOllama:
    provider = provider or cfg.LLM_PROVIDER
    cache_key = f"{provider}_{temperature}"
    if cache_key in _llm_cache:
        return _llm_cache[cache_key]

    if provider == "ollama":
        llm = ChatOllama(temperature=temperature, model=cfg.OLLAMA_MODEL)
    else:
        llm = ChatOpenAI(temperature=temperature, model=cfg.OPENAI_MODEL)

    _llm_cache[cache_key] = llm
    return llm


def get_draft_llm():
    """Cheaper/faster LLM for draft work."""
    return get_llm(provider=cfg.DRAFT_MODEL)


def get_final_llm():
    """Higher-quality LLM for final output."""
    return get_llm(provider=cfg.FINAL_MODEL)
