from pathlib import Path

from bench_runner.main import render_prompt

ROOT = Path(__file__).resolve().parents[1]


def _render(digest, threshold, passed, total, modo):
    msgs = render_prompt(
        "regression-report-generator",
        "0.1.0",
        {"digest": digest, "threshold": threshold, "passed": passed, "total": total, "modo": modo},
    )
    assert [m["role"] for m in msgs] == ["system", "user"]
    return msgs[0]["content"], msgs[1]["content"]


def test_render_json_mode():
    system, user = _render("7/10 en verde", "0.8", 7, 10, "json")
    assert "triador de regresiones" in system
    assert "JSON estricto" in system
    assert "modo: json" in user
    assert "7/10" in user


def test_render_texto_mode():
    system, user = _render("UNA línea", "1.0", 5, 5, "texto")
    assert "modo: texto" in user
    assert "5/5" in user