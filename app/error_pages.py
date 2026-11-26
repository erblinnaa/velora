"""Faqet e gabimeve në stilin e Velora-s."""

from flask import current_app
from flask_wtf.csrf import CSRFError

from .extensions import db


PAGES = {
    400: ("Kërkesa nuk u pranua", "Kthehu mbrapa, rifresko faqen dhe provo përsëri."),
    403: ("Nuk ke qasje këtu", "Kjo faqe nuk është e hapur për llogarinë tënde."),
    404: ("Faqja nuk u gjet", "Adresa mund të jetë e gabuar, ose përmbajtja është fshirë."),
    405: ("Kjo adresë nuk hapet drejtpërdrejt", "Kthehu te faqja e mëparshme dhe përdor butonin përkatës."),
    413: ("Dokumenti është shumë i madh", "Zgjidh një PDF më të vogël ose ngjite vetëm pjesën që të duhet."),
    500: ("Ndodhi një gabim në server", "Veprimi nuk u krye. Provo përsëri pas pak."),
}


def _render(code, title=None, message=None):
    default_title, default_message = PAGES[code]
    # Shabllon i pavarur: nuk lexon përdoruesin, që faqja të shfaqet
    # edhe kur databaza nuk përgjigjet.
    template = current_app.jinja_env.get_template("error.html")
    body = template.render(
        code=code,
        title=title or default_title,
        message=message or default_message,
    )
    return body, code


def register_error_pages(app):
    def handle_http_error(error):
        return _render(error.code)

    for code in (400, 403, 404, 405, 413):
        app.register_error_handler(code, handle_http_error)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        return _render(
            400,
            "Faqja ka skaduar",
            "Për siguri, formulari nuk u dërgua. Kthehu mbrapa, rifresko faqen dhe provo përsëri.",
        )

    @app.errorhandler(500)
    def handle_server_error(error):
        db.session.rollback()
        return _render(500)
