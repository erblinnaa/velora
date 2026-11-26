import logging
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .config import Config
from .extensions import csrf, db, login_manager


def configure_ai_log():
    """Mesazhet e AI shfaqen në terminal me orë, që të gjendet shkaku i vonesave."""
    logger = logging.getLogger("app.ai")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def create_app(test_config=None):
    configure_ai_log()
    load_dotenv()
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models, soft_delete  # noqa: F401
    from .error_pages import register_error_pages
    from .main import main_bp

    app.register_blueprint(main_bp)
    register_error_pages(app)

    with app.app_context():
        soft_delete.ensure_schema()

    @app.cli.command("init-db")
    def init_db_command():
        """Krijon tabelat e databazës PostgreSQL."""
        with app.app_context():
            db.create_all()
            if not soft_delete.ensure_schema():
                from click import ClickException

                raise ClickException(
                    "Databaza nuk u përditësua. Ekzekuto si pronar i tabelave: "
                    + soft_delete.UPGRADE_SQL
                )
        print("Databaza u inicializua me sukses.")

    @app.cli.command("ai-check")
    def ai_check_command():
        """Kontrollon shërbimet AI të konfiguruara (një ose zinxhir)."""
        from click import ClickException
        from .ai.factory import create_provider, provider_names
        from .ai.errors import (
            AIProviderConfigurationError,
            AIProviderError,
        )

        print(f"Rendi i shërbimeve AI: {' -> '.join(provider_names())}")

        try:
            provider = create_provider()
            status = provider.healthcheck()
        except AIProviderConfigurationError as exc:
            raise ClickException(f"Gabim konfigurimi: {exc}") from exc
        except AIProviderError as exc:
            raise ClickException(f"Gabim gjatë kontrollit të API-së: {exc}") from exc

        for item in status.get("providers", [status]):
            state = "po" if item.get("available") else "jo"
            line = f"- {item.get('provider')} ({item.get('model')}): punon = {state}"
            if item.get("error"):
                line += f"  [{item['error']}]"
            print(line)

    return app
