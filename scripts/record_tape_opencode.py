from pathlib import Path

from llm_client import CompletionRequest, CompletionResult, LlmClient, ReplayProvider
from llm_client.providers.opencode_cli import OpenCodeCLI
from schema_validate import SchemaRegistry
from test_kit import EvalCase, EvalDataset, run

from bench_runner.main import DEFAULT_MODEL, SCHEMA_ID, load_prompt, render_prompt
from bench_runner.models import RegressionReport

ROOT = Path(__file__).resolve().parents[1]
PROMPT_FILE = ROOT / "prompts" / "regression-report-generator.md"
DATASET_FILE = ROOT / "evals" / "regression-report-generator.jsonl"
CASSETTES = ROOT / "cassettes"


def main() -> None:
    prompt_id, prompt_version, _, eval_path = load_prompt(PROMPT_FILE)
    dataset = EvalDataset.from_jsonl(DATASET_FILE)

    registry = SchemaRegistry()
    registry.register(SCHEMA_ID, RegressionReport)

    recorder = ReplayProvider(CASSETTES, record=True, inner=OpenCodeCLI(DEFAULT_MODEL))
    client = LlmClient(
        recorder,
        consumer_repo="bench-runner",
        model_aliases={"fast": DEFAULT_MODEL},
        validator=registry.make_validator(SCHEMA_ID),
        renderer=render_prompt,
    )

    def judge(case: EvalCase) -> CompletionResult:
        return client.complete(
            CompletionRequest(
                prompt_id=case.prompt_id,
                prompt_version=case.prompt_version,
                variables=case.input,
                model_alias="fast",
                response_schema=SCHEMA_ID if case.input.get("modo") == "json" else None,
                tags=["record", "seed-week5"],
            )
        )

    report = run(dataset, judge, mode="full", threshold=1.0)
    print(f"grabadas {len(dataset.cases)} respuestas; pass={report.passed}/{report.total}")
    for case_report in report.cases:
        print(case_report.model_dump())


if __name__ == "__main__":
    main()