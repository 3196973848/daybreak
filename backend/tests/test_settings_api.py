from app.config import settings


def test_settings_reflect_configuration_state(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    res = client.get("/api/settings")

    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is False
    assert any(provider["id"] == "ollama" for provider in body["providers"])


def test_settings_update_persists_provider(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr("app.api.settings.save_runtime_conf", lambda **kwargs: None)

    res = client.post(
        "/api/settings",
        json={"provider": "ollama", "model": "qwen2.5"},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "ollama"
    assert body["configured"] is True


def test_settings_update_rejects_unknown_provider(client):
    res = client.post("/api/settings", json={"provider": "unknown-provider"})
    assert res.status_code == 422
