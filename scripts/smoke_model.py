import os
os.sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langchain_core.messages import HumanMessage

from src.config.settings import get_settings
from src.models.huggingface import create_huggingface_model


def main() -> None:
    settings = get_settings()

    model = create_huggingface_model(
        settings,
    )

    response = model.invoke(
        [
            HumanMessage(
                content=(
                    "Reply with exactly: "
                    "VGAR model ready"
                )
            )
        ]
    )

    print(response.content)


if __name__ == "__main__":
    main()