from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./digest.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1):517[3-9]"

    arxiv_categories: str = "cs.LG,cs.AI,cs.CL,cs.CV,stat.ML,quant-ph"
    arxiv_max_results_per_category: int = 40
    lookback_hours: int = 36
    top_n: int = 12
    full_text_top_k: int = 6

    digest_run_time: str = "07:00"
    digest_timezone: str = "UTC"
    enable_scheduler: bool = True

    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.5"
    zai_api_key: str = ""
    zai_base_url: str = "https://api.z.ai/api/paas/v4"
    zai_synthesis_model: str = "glm-5.2"
    zai_classifier_model: str = "glm-4.7-flashx"
    zai_synthesis_input_price_per_m: float = 1.40
    zai_synthesis_output_price_per_m: float = 4.40
    zai_classifier_input_price_per_m: float = 0.07
    zai_classifier_output_price_per_m: float = 0.40
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    llm_run_budget_usd: float = 2.0

    seed_on_empty: bool = True
    log_level: str = "info"
    admin_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def category_list(self) -> list[str]:
        return [category.strip() for category in self.arxiv_categories.split(",") if category.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "openai":
            return bool(self.openai_api_key)
        if self.llm_provider == "zai":
            return bool(self.zai_api_key)
        if self.llm_provider == "anthropic":
            return bool(self.anthropic_api_key)
        return False

    @property
    def llm_setup_hint(self) -> str:
        if self.llm_provider == "zai":
            return "LLM not configured. Add ZAI_API_KEY to run live GLM summarization."
        if self.llm_provider == "openai":
            return "LLM not configured. Add OPENAI_API_KEY to run live summarization."
        return "LLM not configured. Add a provider API key to run live summarization."


@lru_cache
def get_settings() -> Settings:
    return Settings()
