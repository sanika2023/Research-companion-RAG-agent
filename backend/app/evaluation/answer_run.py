"""Ask every evaluation question through the running backend, then check each answer.

Needs the backend running (uvicorn). Results are saved after every request, so rerunning
continues where it stopped. Run from backend/:

    uv run python -m app.evaluation.answer_run                  # answer + 1 check each
    uv run python -m app.evaluation.answer_run --checks 3 --only bb-01,meta-02   # stability
"""

import argparse
import time
from typing import Any

import httpx

from app.evaluation.answers import (
    ANSWERS_PATH,
    AnswerRecord,
    Check,
    checkable,
    load_records,
    plan,
    save_records,
)
from app.evaluation.queries import load_queries
from app.schemas.ask import AskResponse
from app.schemas.diagnose import DiagnoseResponse

BUSY_WAIT_S = 60  # Gemini's per-minute quota resets within a minute
BUSY_RETRIES = 3


def main() -> None:
    args = _parse_args()
    queries = load_queries()
    if args.only:
        wanted = set(args.only.split(","))
        queries = [q for q in queries if q.id in wanted]
    records = load_records()
    steps = plan(queries, records=records, checks=args.checks)
    print(f"{len(steps)} questions to run")

    with httpx.Client(base_url=args.base_url, timeout=300) as client:
        doc_ids = {d["filename"]: d["doc_id"] for d in client.get("/documents").json()}
        for n, step in enumerate(steps, start=1):
            query = step.query
            record = records.setdefault(
                query.id, AnswerRecord(id=query.id, answer=None, ask_seconds=None)
            )
            print(f"[{n}/{len(steps)}] {query.id}: {query.question}")
            doc = doc_ids[query.paper]

            if step.ask:
                result = _post(client, f"/documents/{doc}/ask", {"question": query.question})
                time.sleep(args.pause)
                if isinstance(result, str):
                    record.errors.append(f"ask: {result}")
                    save_records(ANSWERS_PATH, records)
                    continue
                body, seconds = result
                record.answer, record.ask_seconds = AskResponse.model_validate(body), seconds
                save_records(ANSWERS_PATH, records)
                print(f"    answered in {seconds:.1f}s (refused={record.answer.refused})")

            answer = record.answer
            if answer is None or not checkable(answer):
                continue
            request = {
                "question": answer.question,
                "answer": answer.answer,
                "passage_ids": [str(p) for p in answer.passage_ids],
                "sub_questions": answer.sub_questions,
            }
            for _ in range(step.checks):
                result = _post(client, f"/documents/{doc}/diagnose", request)
                time.sleep(args.pause)
                if isinstance(result, str):
                    record.errors.append(f"diagnose: {result}")
                    save_records(ANSWERS_PATH, records)
                    break
                body, seconds = result
                report = DiagnoseResponse.model_validate(body)
                record.checks.append(Check(report=report, seconds=seconds))
                save_records(ANSWERS_PATH, records)
                print(f"    checked in {seconds:.1f}s: risk {report.uncertainty}")


def _post(client: httpx.Client, url: str, body: dict[str, Any]) -> tuple[Any, float] | str:
    """JSON body and seconds taken, or an error description."""
    for attempt in range(BUSY_RETRIES + 1):
        start = time.monotonic()
        try:
            response = client.post(url, json=body)
        except httpx.HTTPError as exc:
            return f"{type(exc).__name__}: {exc}"
        if response.status_code == 503 and attempt < BUSY_RETRIES:
            print(f"    model busy; waiting {BUSY_WAIT_S}s")
            time.sleep(BUSY_WAIT_S)
            continue
        if response.is_error:
            return f"HTTP {response.status_code}: {response.text[:200]}"
        return response.json(), time.monotonic() - start
    raise AssertionError("unreachable")  # the last attempt always returns


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--checks", type=int, default=1, help="answer checks per answer")
    parser.add_argument("--only", help="comma-separated question ids")
    parser.add_argument("--pause", type=float, default=8, help="seconds between requests")
    return parser.parse_args()


if __name__ == "__main__":
    main()
