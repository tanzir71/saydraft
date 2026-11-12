from __future__ import annotations

import argparse
import json
import sys
from dataclasses import astuple, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from saydraft.dictation import DictationConfig, DictationContext, DictationPipeline
from saydraft.dictation.llm_local import LocalLLMConfig


DEFAULT_CORPUS_PATH = Path(__file__).resolve().parents[1] / "tests" / "eval_corpus.jsonl"
DEFAULT_MIN_PASS_RATE = 90.0


@dataclass(frozen=True)
class EvalCase:
    id: str
    input_text: str
    expected: str
    mode: str
    profile: str
    intensity: int | None = None
    app_title: str | None = None
    app_group: str = "general"
    before_caret: str = ""
    language: str = "auto"
    voice_enter_enabled: bool = False
    expected_enter: bool = False
    snippets: tuple[tuple[str, str], ...] = ()
    before_caret_known: bool = False
    selection: str = ""
    selection_known: bool = False
    after_caret: str = ""
    after_caret_known: bool = False
    selection_truncated: bool = False
    tone: str | None = None


@dataclass(frozen=True)
class EvalFailure:
    case: EvalCase
    actual: str
    actual_enter: bool = False


@dataclass(frozen=True)
class EvalResult:
    total: int
    passed: int
    failures: tuple[EvalFailure, ...]

    @property
    def failed(self) -> int:
        return len(self.failures)

    @property
    def pass_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100.0


def _unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field in golden corpus row")
        result[key] = value
    return result


def load_eval_corpus(path: str | Path = DEFAULT_CORPUS_PATH) -> list[EvalCase]:
    corpus_path = Path(path)
    cases: list[EvalCase] = []
    ids, examples = set(), set()
    allowed = {"id", "input", "expected", "mode", "profile", "intensity", "app_title", "app_group", "before_caret",
               "language", "voice_enter_enabled", "expected_enter", "snippets", "before_caret_known",
               "selection", "selection_known", "after_caret", "after_caret_known", "selection_truncated", "tone"}
    with corpus_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            data = json.loads(line, object_pairs_hook=_unique_fields)
            if (not isinstance(data, dict) or set(data) - allowed
                    or any(not isinstance(data.get(key), str) for key in ("id", "input", "expected"))
                    or not data["id"].strip()):
                raise ValueError(f"Invalid fields in golden corpus row {line_number}")
            mode, profile = data.get("mode", "balanced"), data.get("profile", "general")
            intensity = data.get("intensity")
            snippets = data.get("snippets", {})
            if (mode not in ("raw", "balanced", "aggressive")
                    or profile not in ("general", "email", "chat", "notes", "code/comments")
                    or intensity is not None and (type(intensity) is not int or not 0 <= intensity <= 4
                                                  or intensity == 0 and mode != "raw")
                    or data.get("app_title") is not None and not isinstance(data["app_title"], str)
                    or data.get("tone") is not None and (not isinstance(data["tone"], str)
                        or data["tone"] not in ("formal", "casual", "very_casual"))
                    or any(not isinstance(data.get(key, ""), str) for key in (
                        "app_group", "before_caret", "language", "selection", "after_caret"))
                    or len(data.get("after_caret", "")) > 1
                    or any(0xD800 <= ord(char) <= 0xDFFF for char in data.get("after_caret", ""))
                    or any(type(data.get(key, False)) is not bool for key in (
                        "voice_enter_enabled", "expected_enter", "before_caret_known", "selection_known",
                        "after_caret_known", "selection_truncated"))
                    or not isinstance(snippets, dict)
                    or any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) for k, v in snippets.items())
                    or len({key.strip().casefold() for key in snippets}) != len(snippets)):
                raise ValueError(f"Invalid context in golden corpus row {line_number}")
            case = EvalCase(data["id"], data["input"], data["expected"], mode, profile, intensity,
                           data.get("app_title"), data.get("app_group", "general"),
                           data.get("before_caret", ""), data.get("language", "auto"),
                           data.get("voice_enter_enabled", False), data.get("expected_enter", False),
                           tuple(sorted((k.strip().casefold(), v) for k, v in snippets.items())),
                           data.get("before_caret_known", False), data.get("selection", ""),
                           data.get("selection_known", False), data.get("after_caret", ""),
                           data.get("after_caret_known", False), data.get("selection_truncated", False), data.get("tone"))
            signature = astuple(case)[1:]
            if case.id in ids or signature in examples:
                raise ValueError(f"Duplicate ID or example in golden corpus row {line_number}")
            ids.add(case.id)
            examples.add(signature)
            cases.append(case)
    if not cases:
        raise ValueError("Golden corpus is empty")
    return cases


def execute_case(case: EvalCase, pipeline: DictationPipeline):
    """Actual processor ordering with in-memory History and simulated delivery."""
    from types import SimpleNamespace
    from saydraft.core.interfaces import TargetContext
    from saydraft.core.processing import IdentityFormatter, TranscriptProcessor
    from saydraft.insert.inserter import InsertionResult

    context = DictationContext(mode=case.mode, profile=case.profile, intensity=case.intensity,
        app_title=case.app_title, app_group=case.app_group, before_caret=case.before_caret, language=case.language,
        before_caret_known=case.before_caret_known, selection=case.selection, selection_known=case.selection_known,
        after_caret=case.after_caret, after_caret_known=case.after_caret_known,
        selection_truncated=case.selection_truncated, tone=case.tone)
    inserter = SimpleNamespace(insert_text=lambda text, **kw: InsertionResult(
        "inserted", "eval", enter_sent=kw.get("send_enter", False)))
    processor = TranscriptProcessor(cleaner=pipeline, formatter=IdentityFormatter(),
        history=SimpleNamespace(append=lambda entry: 1), inserter=inserter,
        snippets=dict(case.snippets), voice_enter_enabled=case.voice_enter_enabled)
    return processor.process(case.input_text, context=context, model="eval", language=case.language,
        target=TargetContext("eval", case.app_title, app_group=case.app_group, before_caret=case.before_caret,
            before_caret_known=case.before_caret_known, selection=case.selection, selection_known=case.selection_known,
            after_caret=case.after_caret, after_caret_known=case.after_caret_known,
            selection_truncated=case.selection_truncated))


def run_eval(cases: Iterable[EvalCase], pipeline: DictationPipeline | None = None) -> EvalResult:
    active_pipeline = pipeline or DictationPipeline(
        DictationConfig(glossary_path="", llm=LocalLLMConfig(enabled=False)))
    failures: list[EvalFailure] = []
    total = 0
    passed = 0
    for case in cases:
        total += 1
        result = execute_case(case, active_pipeline)
        actual, actual_enter = result.cleaned_text, result.insertion.enter_sent
        if actual == case.expected and actual_enter == case.expected_enter:
            passed += 1
        else:
            failures.append(EvalFailure(case=case, actual=actual, actual_enter=actual_enter))
    return EvalResult(total=total, passed=passed, failures=tuple(failures))


def print_result(result: EvalResult) -> None:
    sys.stdout.write(f"Pass rate: {result.pass_rate:.1f}% ({result.passed}/{result.total} passed)\n")
    if not result.failures:
        return
    sys.stdout.write("Failures:\n")
    for failure in result.failures:
        case = failure.case
        sys.stdout.write(f"- {case.id} [{case.mode}/{case.profile}]\n")
        sys.stdout.write(f"  input:    {case.input_text}\n")
        sys.stdout.write(f"  expected: {case.expected}\n")
        sys.stdout.write(f"  actual:   {failure.actual}\n")
        if case.expected_enter != failure.actual_enter:
            sys.stdout.write(f"  Enter: expected={case.expected_enter}, actual={failure.actual_enter}\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Saydraft dictation golden-file evals.")
    parser.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS_PATH),
        help="Path to JSONL eval corpus.",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=DEFAULT_MIN_PASS_RATE,
        help="Minimum pass rate percentage required for exit code 0.",
    )
    parser.add_argument("--min-cases", type=int, default=1, help="Minimum number of unique golden examples.")
    args = parser.parse_args(argv)
    if not 0 <= args.min_pass_rate <= 100 or args.min_cases < 1:
        parser.error("pass rate must be 0–100 and minimum case count must be positive")

    try:
        result = run_eval(load_eval_corpus(args.corpus))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print_result(result)
    if result.total < args.min_cases:
        sys.stderr.write(f"Corpus too small: {result.total} < {args.min_cases} required.\n")
    return 0 if result.total >= args.min_cases and result.pass_rate >= args.min_pass_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
