"""Standalone Flask server used by Playwright UI tests."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, jsonify
from jinja2 import ChoiceLoader, FileSystemLoader

import coyote
from coyote import init_app
from coyote.services.api_client.api_client import CoyoteApiClient
from tests.e2e.fake_ui_api import E2EApiState

STATE = E2EApiState()


def create_app() -> Flask:
    """Create the Playwright-target Flask app with API stubs installed."""
    coyote.verify_external_api_dependency = lambda _app: None

    def fake_get(self, path, headers=None, params=None):  # noqa: ARG001
        return STATE.get_json(path, params=params)

    def fake_post(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return STATE.post_json(path, json_body=json_body)

    def fake_patch(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return STATE.patch_json(path)

    def fake_put(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return STATE.put_json(path, json_body=json_body)

    def fake_delete(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return STATE.delete_json(path)

    CoyoteApiClient.get_json = fake_get
    CoyoteApiClient.post_json = fake_post
    CoyoteApiClient.patch_json = fake_patch
    CoyoteApiClient.put_json = fake_put
    CoyoteApiClient.delete_json = fake_delete
    CoyoteApiClient.last_response_cookie = lambda self, name: STATE.session_token  # noqa: ARG005

    app = init_app(testing=True)
    app.config.update(
        WTF_CSRF_ENABLED=False,
        LOGIN_DISABLED=False,
        TESTING=False,
        PROPAGATE_EXCEPTIONS=True,
    )
    e2e_templates = Path(__file__).resolve().parent / "templates"
    app.jinja_loader = ChoiceLoader([app.jinja_loader, FileSystemLoader(str(e2e_templates))])

    @app.post("/__e2e__/reset")
    def reset_state():
        STATE.reset()
        return jsonify({"status": "ok"})

    return app


APP = create_app()


if __name__ == "__main__":
    APP.run(host="127.0.0.1", port=int(os.environ.get("E2E_PORT", "4173")), use_reloader=False)
