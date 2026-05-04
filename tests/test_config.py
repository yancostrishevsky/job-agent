from app.config.loader import load_runtime_config


def test_runtime_config_reads_llm_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("JOB_AGENT_LLM_ENABLED", "true")
    monkeypatch.setenv("JOB_AGENT_LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("JOB_AGENT_LLM_RERANK_TOP_K", "5")
    monkeypatch.setenv("JOB_AGENT_LLM_COMPARISON_ENABLED", "true")
    monkeypatch.setenv("JOB_AGENT_LLM_COMPARISON_MODELS", "qwen3:4b,gemma3:4b")

    config = load_runtime_config()

    assert config.llm.enabled is True
    assert config.llm.model == "qwen3:8b"
    assert config.llm.rerank_top_k == 5
    assert config.llm.comparison_enabled is True
    assert config.llm.comparison_models == ["qwen3:4b", "gemma3:4b"]
