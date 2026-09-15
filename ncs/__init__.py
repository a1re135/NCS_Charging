"""Application factory: configuration, CSRF protection, API errors, database setup."""
import os
import secrets
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from flask import Flask, jsonify, request, session, render_template
from .db import close_db, init_db
from .services import BusinessError

def create_app(config=None):
    root=Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")
    app=Flask(__name__,template_folder=str(root/'templates'),static_folder=str(root/'static'))
    data=root/'data'; data.mkdir(exist_ok=True)
    secret=data/'secret.key'
    if not secret.exists():
        try:
            with secret.open('x',encoding='utf-8') as f: f.write(secrets.token_hex(32))
        except FileExistsError: pass
    app.config.update(
        SECRET_KEY=os.getenv("NCS_SECRET_KEY") or secret.read_text().strip(),

        DB_BACKEND=os.getenv("DB_BACKEND", "mysql"),

        DATABASE=str(data / "ncs.db"),

        MYSQL_HOST=os.getenv("MYSQL_HOST", "localhost"),
        MYSQL_PORT=int(os.getenv("MYSQL_PORT", "3306")),
        MYSQL_DATABASE=os.getenv("MYSQL_DATABASE", "ncs_charging"),
        MYSQL_USER=os.getenv("MYSQL_USER", "ncs_app"),
        MYSQL_PASSWORD=os.getenv("MYSQL_PASSWORD", ""),

        TIME_SCALE=60,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
)
    if config: app.config.update(config)
    backend = app.config.get("DB_BACKEND", "sqlite")

    if backend == "mysql":
        print(
            f"[Database] MySQL "
            f"{app.config['MYSQL_HOST']}:"
            f"{app.config['MYSQL_PORT']}/"
            f"{app.config['MYSQL_DATABASE']}"
        )
    else:
        print(
            f"[Database] SQLite "
            f"{app.config['DATABASE']}"
        )
    app.teardown_appcontext(close_db)
    @app.before_request
    def csrf_check():
        if request.path.startswith('/api/') and request.method not in ('GET','HEAD','OPTIONS'):
            supplied=request.headers.get('X-CSRF-Token','')
            if not supplied or not secrets.compare_digest(supplied,session.get('csrf','')):
                raise BusinessError('页面会话已过期，请刷新页面后重试',403)
    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        if request.path.startswith('/api/'): response.headers['Cache-Control']='no-store'
        return response
    @app.errorhandler(BusinessError)
    def business_error(e): return jsonify(error=e.message,**e.extra),e.status
    @app.errorhandler(pymysql.err.IntegrityError)
    def integrity_error(e):
        return jsonify(
            error="数据冲突：编号已存在、资源正在使用，或记录仍被其他数据引用"
    ), 409
    @app.errorhandler(400)
    def bad_request(e): return jsonify(error='请求格式不正确'),400
    @app.errorhandler(413)
    def too_large(e): return jsonify(error='文件或请求过大，最多 2 MB'),413
    @app.get('/')
    @app.get('/charge/<charger_number>')
    def index(charger_number=None): return render_template('index.html')
    from .routes import api
    app.register_blueprint(api,url_prefix='/api')
    with app.app_context(): init_db()
    return app
