from swe_agent.config import DEFAULT_MODEL, load_settings


def test_defaults_when_env_empty():
    s = load_settings(env={})
    assert s.anthropic_api_key is None
    assert not s.has_llm_key
    assert s.model == DEFAULT_MODEL
    assert s.max_patch_retries == 2
    assert s.sandbox_timeout_seconds == 120


def test_values_read_from_env():
    s = load_settings(
        env={
            "ANTHROPIC_API_KEY": "test-not-a-real-key",
            "ANTHROPIC_MODEL": "some-model",
            "MAX_PATCH_RETRIES": "1",
            "SANDBOX_CPUS": "0.5",
        }
    )
    assert s.has_llm_key
    assert s.model == "some-model"
    assert s.max_patch_retries == 1
    assert s.sandbox_cpus == 0.5
