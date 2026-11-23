from app.core.config import settings
from app.core.logging import configure_logging


def main() -> None:
    configure_logging(settings.log_level)
    from rq.cli.cli import main as rq_main

    rq_main()


if __name__ == "__main__":
    main()
