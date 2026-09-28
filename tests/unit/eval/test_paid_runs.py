"""`eval/paid_runs.py`: the shared loop and cost policy (refactor-paid-runs, ticket 03), against
fake jobs only — no API call, no real model."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from eval.paid_runs import (
    ESTIMATED_COST_KEY,
    REAL_COST_KEY,
    CostCapExceededError,
    CostPolicy,
    OverOneDollarError,
    RunOutcome,
    UnknownModelError,
    load_records,
    run_paid_jobs,
)


def _policy(
    price_per_job: float = 0.01, max_cost_usd: float = 1.0, approved_over_1usd: bool = False
) -> CostPolicy:
    return CostPolicy(
        model="fake",
        price=lambda i, o: price_per_job,
        input_tokens_per_job=100,
        output_tokens_per_job=50,
        max_cost_usd=max_cost_usd,
        approved_over_1usd=approved_over_1usd,
    )


def _run_one(estimated: float = 0.01, real: float | None = None) -> Any:
    def run_one(job: str) -> dict[str, Any]:
        return {"job": job, ESTIMATED_COST_KEY: estimated, REAL_COST_KEY: real}

    return run_one


def _run(
    jobs: list[str], tmp_path: Path, *, cost_policy: CostPolicy, run_one: Any = None, **kwargs: Any
) -> RunOutcome:
    return run_paid_jobs(
        jobs,
        run_one=run_one or _run_one(),
        key=lambda j: j,
        record_key=lambda r: r["job"],
        cost_policy=cost_policy,
        out_file=tmp_path / "runs.jsonl",
        log=lambda _: None,
        **kwargs,
    )


def test_every_job_is_stored_and_resume_skips_done_keys(tmp_path: Path) -> None:
    outcome = _run(["a", "b", "c"], tmp_path, cost_policy=_policy())
    assert (outcome.ran, outcome.skipped_done) == (3, 0)
    records = load_records(tmp_path / "runs.jsonl")
    assert sorted(r["job"] for r in records) == ["a", "b", "c"]

    resumed = _run(["a", "b", "c", "d"], tmp_path, cost_policy=_policy())
    assert (resumed.ran, resumed.skipped_done) == (1, 3)
    assert sorted(r["job"] for r in load_records(tmp_path / "runs.jsonl")) == ["a", "b", "c", "d"]


def test_a_crash_is_logged_and_not_written_so_it_is_retried(tmp_path: Path) -> None:
    def boom(job: str) -> dict[str, Any]:
        raise ConnectionError("openrouter down")

    outcome = _run(["a", "b"], tmp_path, cost_policy=_policy(), run_one=boom)
    assert (outcome.ran, outcome.crashed) == (0, 2)
    assert load_records(tmp_path / "runs.jsonl") == []


def test_the_cost_cap_stops_new_jobs(tmp_path: Path) -> None:
    # The declared per-job estimate (0.1, used for the upfront gate and the reservation) is a
    # lower bound on what a real run actually costs (0.3, recorded per job): the upfront estimate
    # for 5 jobs (0.5) clears the $1.0 cap, but the 4th job's reservation trips once the first
    # three have actually spent 0.9 — the real per-record cost, not the declared one, is what the
    # cap is checked against as jobs complete.
    outcome = _run(
        ["a", "b", "c", "d", "e"],
        tmp_path,
        cost_policy=_policy(price_per_job=0.15, max_cost_usd=1.0),
        run_one=_run_one(estimated=0.3),
    )
    assert outcome.ran == 3
    assert outcome.skipped_budget == 2
    assert outcome.estimated_cost_usd == pytest.approx(0.9)


def test_an_unknown_model_is_refused_before_anything_runs(tmp_path: Path) -> None:
    policy = CostPolicy.for_model(
        "totally/unpriced-model",
        input_tokens_per_job=100,
        output_tokens_per_job=50,
        max_cost_usd=5.0,
    )
    with pytest.raises(UnknownModelError):
        _run(["a"], tmp_path, cost_policy=policy)
    assert load_records(tmp_path / "runs.jsonl") == []


def test_an_estimate_over_one_dollar_is_refused_without_the_flag_and_allowed_with_it(
    tmp_path: Path,
) -> None:
    policy = _policy(price_per_job=0.5, max_cost_usd=10.0)
    with pytest.raises(OverOneDollarError):
        _run(["a", "b", "c"], tmp_path, cost_policy=policy, run_one=_run_one(estimated=0.5))

    approved = _policy(price_per_job=0.5, max_cost_usd=10.0, approved_over_1usd=True)
    outcome = _run(["a", "b", "c"], tmp_path, cost_policy=approved, run_one=_run_one(estimated=0.5))
    assert outcome.ran == 3


def test_an_estimate_over_the_cap_is_refused_at_the_start_not_mid_run(tmp_path: Path) -> None:
    policy = _policy(price_per_job=0.5, max_cost_usd=0.9, approved_over_1usd=True)
    with pytest.raises(CostCapExceededError):
        _run(["a", "b", "c"], tmp_path, cost_policy=policy, run_one=_run_one(estimated=0.5))
    # refused before the first job starts: nothing was written
    assert load_records(tmp_path / "runs.jsonl") == []


def test_workers_above_one_reserve_in_flight_jobs_before_they_complete(tmp_path: Path) -> None:
    """Regression test for the bug this module fixes (spec "Why"): with N workers, up to N jobs
    used to start after the last check that saw spend under the cap, because that check only
    looked at completed spend. Here a `threading.Barrier` forces the first 5 (of 8 pending) jobs
    to be reserved and in flight *together*, simultaneously, before any of them completes and
    updates `spent` — the declared per-job estimate (0.11) is loose enough that none of the 5 is
    blocked at the reservation step itself, but tight enough that a single completion (real cost
    0.5) already pushes any 6th reservation over the cap. Once the first of the 5 completes, no
    freed worker can start a 6th/7th/8th job: the in-flight count, not just completed spend, is
    what a new reservation is checked against.
    """
    workers = 5
    barrier = threading.Barrier(workers)

    def run_one(job: str) -> dict[str, Any]:
        barrier.wait(timeout=5)
        return {"job": job, ESTIMATED_COST_KEY: 0.5, REAL_COST_KEY: None}

    jobs = [str(i) for i in range(8)]
    policy = _policy(price_per_job=0.11, max_cost_usd=1.0, approved_over_1usd=True)
    outcome = _run(jobs, tmp_path, cost_policy=policy, run_one=run_one, workers=workers)
    assert outcome.ran == workers
    assert outcome.skipped_budget == len(jobs) - workers
    assert outcome.estimated_cost_usd == pytest.approx(workers * 0.5)


def test_real_cost_is_reported_only_when_every_ran_job_reported_it(tmp_path: Path) -> None:
    known = _run(
        ["a", "b"], tmp_path, cost_policy=_policy(), run_one=_run_one(estimated=0.01, real=0.02)
    )
    assert known.real_cost_usd == pytest.approx(0.04)

    unknown = _run(
        ["c", "d"],
        tmp_path,
        cost_policy=_policy(),
        run_one=_run_one(estimated=0.01, real=None),
    )
    assert unknown.real_cost_usd is None
    assert unknown.estimated_cost_usd == pytest.approx(0.02)
