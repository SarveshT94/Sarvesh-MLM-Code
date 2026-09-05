"""
run.py — REWRITE

Local development entrypoint ONLY.

In production you must NOT use Flask's built-in server (debug=True exposes the
Werkzeug interactive debugger = remote code execution). Production runs under
gunicorn + gevent (see deploy/gunicorn.conf.py and deploy/deployment.md):

    gunicorn -c deploy/gunicorn.conf.py "app:create_app()"

This file keeps `python run.py` working for local dev with debug OFF unless
FLASK_DEBUG=1 is explicitly set.
"""
from app import create_app
from app.utils.logger import setup_logging
from app.config.config import get_config

setup_logging()
cfg = get_config()
app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(__import__("os").environ.get("PORT", 5000)),
        debug=cfg.DEBUG and cfg.ENV != "production",
        use_reloader=cfg.DEBUG and cfg.ENV != "production",
    )
