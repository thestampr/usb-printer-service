"""Flask application exposing a USB receipt printer endpoint."""
from __future__ import annotations

from flask import Blueprint, Flask, jsonify, request
from flask_cors import CORS

from common.interface import PayloadInfo
from config import settings
from l10n import LocaleEN, LocaleTH
from printer.driver import ReceiptPrinter
from printer.template import validate_payload, apply_payload_images
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
    layout_cfg = dict(current_config.get("LAYOUT", {}))
    apply_payload_images(layout_cfg, validated.get("images"))

    # Render in the configured receipt locale (Layout -> receipt_locale).
    locale = LocaleTH() if layout_cfg.get("receipt_locale", "en") == "th" else LocaleEN()

    info = PayloadInfo.from_dict(validated)
    img = generate_receipt_image(
        layout_cfg,
        info,
        locale=locale,
    )
    printer = ReceiptPrinter(printer_cfg)

    try:
        printer.print_image(img)
        printer.cut()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        printer.disconnect()

    return jsonify({"status": "printed", "total": info.total}), 200

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


@printer_bp.route("/docs", methods=["GET"])
def get_docs():
    import os
    from flask import send_from_directory
    
    docs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    return send_from_directory(docs_path, "docs.html")


def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)
    app.register_blueprint(printer_bp)
    return app
