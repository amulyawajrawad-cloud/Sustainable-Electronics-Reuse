"""One consistent JSON error shape: {"error": {"code", "message", "fields"?}}."""
from flask import jsonify, request


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, fields: dict | None = None):
        super().__init__(message)
        self.status, self.code, self.message, self.fields = status, code, message, fields


def _payload(code, message, fields=None):
    err = {"code": code, "message": message}
    if fields:
        err["fields"] = fields
    return {"error": err}


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def api_error(e):
        return jsonify(_payload(e.code, e.message, e.fields)), e.status

    @app.errorhandler(404)
    def not_found(_e):
        if request.path.startswith("/api/"):
            return jsonify(_payload("not_found", "Resource not found.")), 404
        return "Not found", 404

    @app.errorhandler(405)
    def bad_method(_e):
        return jsonify(_payload("method_not_allowed", "Method not allowed.")), 405

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify(_payload("too_large", "Upload too large (max 8 MB per request).")), 413

    @app.errorhandler(500)
    def server_error(_e):
        return jsonify(_payload("server_error", "Something went wrong on our side.")), 500
