from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

import yaml
from llm_client import CompletionRequest, CompletionResult, LlmClient, ReplayProvider, Span
from llm_client.providers.opencode_cli import OpenCodeCLI
from schema_validate import SchemaRegistry
from test_kit import DatasetError, EvalCase, EvalDataset, run

from .models import RegressionReport

DEFAULT_MODEL = "opencode/big-pickle"
SCHEMA_ID = "regression-report-v1"
ROOT = Path(__file__).resolve().parents[2]
PROMPT_DIR = ROOT / "prompts"
DEFAULT_PROMPT = PROMPT_DIR / "regression-report-generator.md"


def load_prompt(path: Path) -> tuple[str, str, str, Path]:
    text = path.read_text()
    if not text.startswith("---"):
        raise SystemExit(f"{path}: falta frontmatter")
    _, frontmatter, body = text.split("---", 2)
    data = yaml.safe_load(frontmatter)
    eval_path = ROOT / data["eval"] if not Path(data["eval"]).is_absolute() else Path(data["eval"])
    return data["id"], data["version"], body.strip(), eval_path


def render_prompt(prompt_id: str, prompt_version: str, variables: dict) -> list[dict]:
    _, _, body, _ = load_prompt(DEFAULT_PROMPT)
    system_part = body.split("## Sistema\n", 1)[1].split("## Usuario\n", 1)[0].strip()
    user_part = body.split("## Usuario\n", 1)[1].strip().format(
        digest=variables["digest"],
        threshold=variables["threshold"],
        passed=variables["passed"],
        total=variables["total"],
        modo=variables["modo"],
    )
    return [
        {"role": "system", "content": system_part},
        {"role": "user", "content": user_part},
    ]


def build_emitter(span_file: Path | None):
    def emit(span: Span, _result) -> None:
        if span_file is not None:
            with span_file.open("a") as handle:
                handle.write(span.as_jsonl() + "\n")
        else:
            sys.stderr.write(span.as_jsonl() + "\n")

    return emit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench-runner", description="Evals de prompts: los tests son datasets (test-kit).")
    parser.add_argument("--dataset", default=None, help="dataset .jsonl (default: el del frontmatter del prompt)")
    parser.add_argument("--prompt", default=str(DEFAULT_PROMPT), help="prompt con frontmatter")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"modelo opencode (default: {DEFAULT_MODEL})")
    parser.add_argument("--replay", metavar="DIR", default=None, help="reproducir cassettes sin tocar el LLM")
    parser.add_argument("--record", metavar="DIR", default=None, help="grabar cassettes reales (record)")
    parser.add_argument("--mode", choices=["smoke", "full"], default="smoke", help="smoke: diario · full: releases")
    parser.add_argument("--threshold", type=float, default=1.0, help="fracción mínima de casos en verde [0,1]")
    parser.add_argument("--span-file", metavar="PATH", default=None, help="escribir spans a JSONL")
    args = parser.parse_args(argv)

    prompt_id, prompt_version, _, eval_path = load_prompt(Path(args.prompt))
    dataset_path = Path(args.dataset) if args.dataset else eval_path

    try:
        dataset = EvalDataset.from_jsonl(dataset_path)
    except DatasetError as exc:
        sys.stderr.write(f"bench-runner: dataset inválido: {exc}\n")
        return 2

    if dataset.prompt_id != prompt_id or dataset.prompt_version != prompt_version:
        sys.stderr.write(
            f"bench-runner: dataset referencia {dataset.prompt_id}@{dataset.prompt_version}, "
            f"el prompt es {prompt_id}@{prompt_version}\n"
        )
        return 2

    if args.replay:
        provider = ReplayProvider(args.replay, record=False)
    elif args.record:
        provider = ReplayProvider(args.record, record=True, inner=OpenCodeCLI(args.model))
    else:
        provider = OpenCodeCLI(args.model)

    registry = SchemaRegistry()
    registry.register(SCHEMA_ID, RegressionReport)

    client = LlmClient(
        provider,
        consumer_repo="bench-runner",
        model_aliases={"fast": args.model},
        emitter=build_emitter(Path(args.span_file) if args.span_file else None),
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
                tags=["bench-runner", "week-5"],
            )
        )

    report = run(dataset, judge, mode=args.mode, threshold=args.threshold)
    print(report.model_dump_json(indent=2))

    if not report.threshold_ok:
        sys.stderr.write(f"bench-runner: REGRESIÓN — {report.passed}/{report.total} casos pasan (umbral {args.threshold})\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())