"""Application factory: configuration, CSRF protection, API errors, database setup."""

import os
import secrets
from decimal import Decimal
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, render_template
from flask.json.provider import DefaultJSONProvider
from werkzeug.middleware.proxy_fix import ProxyFix

from .db import close_db, init_db
from .services import BusinessError
from .i18n import translate, current_language


def create_app(config=None):
    root = Path(__file__).resolve().parent.parent

    load_dotenv(root / ".env")

    app = Flask(
        __name__,
        template_folder=str(root / "templates"),
        static_folder=str(root / "static"),
    )

    # MySQL returns DECIMAL for SUM/AVG aggregates; serialize as numbers
    # instead of strings so front-end arithmetic never concatenates.
    class _NCSJSONProvider(DefaultJSONProvider):
        def default(self, o):
            if isinstance(o, Decimal):
                return int(o) if o == o.to_integral_value() else float(o)
            return super().default(o)

    app.json_provider_class = _NCSJSONProvider
    app.json = _NCSJSONProvider(app)

    data = root / "data"
    data.mkdir(exist_ok=True)

    secret = data / "secret.key"

    if not secret.exists():
        try:
            with secret.open("x", encoding="utf-8") as f:
                f.write(secrets.token_hex(32))
        except FileExistsError:
            pass

    app.config.update(
        SECRET_KEY=(
            os.getenv("NCS_SECRET_KEY")
            or os.getenv("SECRET_KEY")
            or secret.read_text().strip()
        ),

        # MySQL
        MYSQL_HOST=os.getenv("MYSQL_HOST", "localhost"),
        MYSQL_PORT=int(os.getenv("MYSQL_PORT", "3306")),
        MYSQL_DATABASE=os.getenv("MYSQL_DATABASE", "ncs_charging"),
        MYSQL_USER=os.getenv("MYSQL_USER", "ncs_app"),
        MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD", ""),
        TIME_SCALE=60,
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.getenv("NCS_COOKIE_SECURE", "0").lower() in ("1", "true", "yes"),
        TRUST_PROXY=os.getenv("NCS_TRUST_PROXY", "0").lower() in ("1", "true", "yes"),
        NCS_BACKUP_DIR=os.getenv("NCS_BACKUP_DIR", ""),
    )

    if config:
        app.config.update(config)

    print(
        f"[Database] MySQL "
        f"{app.config['MYSQL_HOST']}:"
        f"{app.config['MYSQL_PORT']}/"
        f"{app.config['MYSQL_DATABASE']}"
    )

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_port=1,
        )

    app.teardown_appcontext(close_db)

    @app.before_request
    def csrf_check():
        if request.path.startswith("/api/") and request.method not in ("GET", "HEAD", "OPTIONS"):
            supplied = request.headers.get("X-CSRF-Token", "")
            if not supplied or not secrets.compare_digest(supplied, session.get("csrf", "")):
                raise BusinessError("页面会话已过期，请刷新页面后重试", 403)

    @app.after_request
    def headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Content-Language"] = current_language()
        return response

    @app.errorhandler(BusinessError)
    def business_error(e):
        return jsonify(
            error=translate(e.message),
            **e.extra,
        ), e.status
    
    @app.errorhandler(pymysql.err.IntegrityError)
    def integrity_error(e):
        return jsonify(error=translate("数据冲突：编号已存在、资源正在使用，或记录仍被其他数据引用")), 409

    @app.errorhandler(400)
    def bad_request(e):
        return jsonify(error=translate("请求格式不正确")), 400

    @app.errorhandler(413)
    def too_large(e):
        return jsonify(error=translate("文件或请求过大，最多 6 MB（头像图片最多 5 MB）")), 413

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/charge/<string:charger_number>")
    def charge_page(charger_number):
        return render_template("index.html")

    from .routes import api
    from .ops_features import ops_api
    from .loyalty import member_api

    app.register_blueprint(api, url_prefix="/api")
    app.register_blueprint(ops_api, url_prefix="/api")
    app.register_blueprint(member_api, url_prefix="/api")

    with app.app_context():
        init_db()

    return app