from __future__ import annotations

from vgar.agents.workflow import app


def main() -> None:
    """Offline smoke test: the outer workflow compiles and has the expected shape."""
    print(app.get_graph().draw_mermaid())


if __name__ == "__main__":
    main()
