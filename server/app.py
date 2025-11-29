"""Flask application exposing a USB receipt printer endpoint."""
from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request
from flask_cors import CORS

from config.settings import LAYOUT, PRINTER
from printer.driver import ReceiptPrinter
from printer.template import build_receipt_text, validate_payload

printer_bp = Blueprint("printer", __name__)


@printer_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@printer_bp.route("/print", methods=["POST"])
def print_receipt():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:  # pragma: no cover - handled by Flask
        return jsonify({"error": "Invalid JSON body"}), 400

    try:
        validated = validate_payload(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    receipt_text = build_receipt_text(validated)

    printer = ReceiptPrinter(PRINTER)
    header_image = LAYOUT.get("header_image")
    footer_image = LAYOUT.get("footer_image")

    try:
        if header_image:
            printer.print_image(header_image)
        printer.print_text(receipt_text)
        if footer_image:
            printer.print_image(footer_image)
        printer.feed(2)
        printer.cut()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        printer.disconnect()

    return jsonify({"status": "printed", "total": validated["total"]}), 200

@printer_bp.route("/open-drawer", methods=["POST"])
def open_drawer():
    try:
        printer = ReceiptPrinter(PRINTER)
        printer.kick_drawer()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        printer.disconnect()
    return jsonify({"status": "drawer opened"}), 200


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(printer_bp)
    return app
