"""Flask application exposing a USB receipt printer endpoint."""
from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request
from flask_cors import CORS

from common.interface import PayloadInfo
from config import settings
from printer.driver import ReceiptPrinter
from printer.template import validate_payload
from printer.renderer import generate_receipt_image

printer_bp = Blueprint("printer", __name__)


@printer_bp.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@printer_bp.route("/print", methods=["POST"])
def print_receipt():
    try:
        payload = request.get_json(force=True, silent=False)
    except Exception:
        return jsonify({"error": "Invalid JSON body"}), 400

    try:
        validated = validate_payload(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    
    current_config = settings.get_all()
    printer_cfg = current_config.get("PRINTER", {})
    layout_cfg = current_config.get("LAYOUT", {})

    info = PayloadInfo.from_dict(validated)
    img = generate_receipt_image(
        layout_cfg,
        info
    )
    printer = ReceiptPrinter(printer_cfg)

    try:
        printer.print_image(img)
        printer.cut()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        printer.disconnect()

    return jsonify({"status": "printed", "total": validated["total"]}), 200

@printer_bp.route("/open-drawer", methods=["POST"])
def open_drawer():
    current_config = settings.get_all()
    printer_cfg = current_config.get("PRINTER", {})

    try:
        printer = ReceiptPrinter(printer_cfg)
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
