"""F7: both tiers of the backend decide with the configured gated fusion (T2.5, T4.1)."""
import inspect

from backend import final_config, tier1


def test_config_names_gated_fusion():
    assert final_config.config()["enforcement"]["form"]["value"] == "gated"


def test_high_anomaly_blocks_whatever_the_sensitivity():
    tau_a = final_config.val("enforcement", "tau_A")
    assert final_config.decide(0.0, min(1.0, tau_a + 1e-6))["action"] == "BLOCK"


def test_low_anomaly_follows_the_bands():
    t_alert = final_config.val("enforcement", "t_alert")
    assert final_config.decide(0.0, 0.0)["action"] == "PERMIT"
    assert final_config.decide(100.0, 0.0)["action"] in ("ALERT", "BLOCK") or t_alert > 1.0


def test_both_tiers_call_decide():
    assert "decide(" in inspect.getsource(tier1.tier1_score)
    assert "decide(" in inspect.getsource(tier1._run_tier2)


def test_no_text_cutoff_without_config_or_env(monkeypatch):
    monkeypatch.delenv("HYBRIDSAAS_TIER1_MAX_TEXT_BYTES", raising=False)
    if "tier1" not in final_config.config():
        assert tier1.text_cutoff_bytes() is None


def test_env_overrides_text_cutoff(monkeypatch):
    monkeypatch.setenv("HYBRIDSAAS_TIER1_MAX_TEXT_BYTES", "2048")
    assert tier1.text_cutoff_bytes() == 2048
    monkeypatch.setenv("HYBRIDSAAS_TIER1_MAX_TEXT_BYTES", "0")
    assert tier1.text_cutoff_bytes() is None
