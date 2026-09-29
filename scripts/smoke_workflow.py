from __future__ import annotations

import asyncio

from vgar.agents.workflow import app


async def main() -> None:
    result = await app.ainvoke(
        {
            "task_id": "smoke-001",
            "repo_path": ".",
            "issue_text": (
                "Smoke test VGAR outer workflow."
            ),
            "failing_tests": [],
            "max_iterations": 5,
        }
    )

    print(result)


if __name__ == "__main__":
    asyncio.run(main())