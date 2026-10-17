"""Real-model retrieval acceptance check and warm CPU latency measurement."""
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from core.config import AppError
from core.db import Assignment, session_scope
from core.retrieval import retrieve


def main() -> None:
    """Find seeded evidence in the top three and measure one warm query."""
    with session_scope() as session:
        assignment = session.scalar(select(Assignment).where(Assignment.title == "Physics diagnostic"))
        if not assignment:
            raise AppError("Run scripts/seed_demo.py first.")
    query = (assignment.classroom_id, "Q1", "Define force and its unit", "Force equals mass times acceleration; measured in newtons.")
    retrieve(*query)  # Model initialization is excluded from the warm CPU benchmark.
    start = time.perf_counter()
    results = retrieve(*query)
    elapsed = time.perf_counter() - start
    assert any("force" in d.text.lower() for d in results[:3]), "Known notes missing from top three"
    assert elapsed < 5, f"Warm CPU retrieval took {elapsed:.2f}s (target <5s)"
    print(f"PASS: related evidence in top three; warm retrieval {elapsed:.2f}s")


if __name__ == "__main__":
    main()
