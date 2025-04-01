import threading
from flask import Blueprint, request, jsonify
from app import db
from app.models import FitnessCategory, Mapping
from app.logger import add_log, clear_logs, get_logs
from app.services.emag_full_seq import (
    run_create_process,
    run_update_process,
    fetch_all_emag_products,
    fetch_all_fitness1_products,
)
from app.services import const
from app.services import util

api_bp = Blueprint("api", __name__, url_prefix="/api")


@api_bp.route("/create", methods=["POST"])
def api_create():
    """
    Endpoint to trigger the product creation process.
    Accepts a JSON payload with optional parameters: 'pause' and 'batch_size'.
    """
    data = request.get_json() or {}
    pause = data.get("pause", 1)
    batch_size = data.get("batch_size", 50)

    add_log("API /create endpoint called.")
    result = {}

    def run_create():
        try:
            add_log("Starting product creation process...")
            # Call our refactored create function.
            summary = run_create_process(pause=pause, batch_size=batch_size)
            add_log("Product creation process completed successfully.")
            result.update(
                {
                    "status": "success",
                    "message": "Product creation process executed.",
                    "summary": summary,
                }
            )
        except Exception as e:
            add_log(f"Error in product creation process: {str(e)}")
            result.update({"status": "error", "message": str(e)})

    # Run the create process in a thread so the API remains responsive.
    create_thread = threading.Thread(target=run_create)
    create_thread.start()
    create_thread.join()  # Wait for process to complete so we can return a complete result

    return jsonify(result)


@api_bp.route("/update", methods=["POST"])
def api_update():
    """
    Endpoint to trigger the product update process.
    Accepts a JSON payload with optional parameters: 'pause' and 'batch_size'.
    Runs the update process synchronously.
    """
    data = request.get_json() or {}
    pause = data.get("pause", 1)
    batch_size = data.get("batch_size", 50)

    add_log("API /update endpoint called.")
    result = {}

    try:
        # Call our refactored update function.
        summary = run_update_process(pause=pause, batch_size=batch_size)
        if summary["emag_products_fetched"] == 0:
            add_log("No EMAG products to update.")
        else:
            add_log("Product update process completed successfully.")
        result.update(
            {
                "status": "success",
                "message": "Product update process executed.",
                "summary": summary,
            }
        )
    except Exception as e:
        add_log(f"Error in product update process: {str(e)}")
        result.update({"status": "error", "message": str(e)})

    return jsonify(result)


@api_bp.route("/logs", methods=["GET"])
def api_logs():
    """
    Returns the in-memory logs as a JSON response.
    """
    logs = get_logs()
    return jsonify({"logs": logs})


@api_bp.route("/logs/clear", methods=["POST"])
def api_clear_logs():
    clear_logs()
    return jsonify({"status": "success", "message": "Logs cleared."})


@api_bp.route("/products/fitness1", methods=["GET"])
def api_get_fitness1_products():
    # Use your existing function to fetch Fitness1 products
    products = fetch_all_fitness1_products(
        api_url=const.FITNESS1_API_URL, api_key=const.FITNESS1_API_KEY
    )
    # Optionally, you could process these into dicts if neededog
    return jsonify({"products": products})


@api_bp.route("/products/emag", methods=["GET"])
def api_get_emag_products():
    products = fetch_all_emag_products(
        api_url=util.build_url(const.EMAG_URL, "product_offer", "read"),
        headers=const.EMAG_HEADERS,
        pause=1,
    )
    return jsonify({"products": products})


@api_bp.route("/mappings", methods=["GET"])
def api_get_mappings():
    mappings = Mapping.query.all()
    return jsonify({"mappings": {m.id: m.as_dict() for m in mappings}})


@api_bp.route("/mappings", methods=["POST"])
def api_create_mapping():
    data = request.get_json() or {}
    fitness1_cat = data.get("fitness1_category")
    emag_cat = data.get("emag_category")
    if not (fitness1_cat and emag_cat):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Both fitness1_category and emag_category are required.",
                }
            ),
            400,
        )
    new_mapping = Mapping(fitness1_category=fitness1_cat, emag_category=emag_cat)
    db.session.add(new_mapping)
    db.session.commit()
    return jsonify({"status": "success", "mapping": new_mapping.as_dict()}), 201


@api_bp.route("/mappings", methods=["PATCH"])
def api_update_mappings():
    # Expect a list of mapping updates
    data = request.get_json() or {}
    updates = data.get("updates", [])
    if not updates:
        return jsonify({"status": "error", "message": "No updates provided."}), 400
    for update in updates:
        mapping_id = update.get("id")
        new_emag_cat = update.get("emag_category")
        if mapping_id and new_emag_cat:
            mapping = Mapping.query.get(mapping_id)
            if mapping:
                mapping.emag_category = new_emag_cat
    db.session.commit()
    return jsonify({"status": "success", "message": "Mappings updated."})


@api_bp.route("/categories", methods=["GET"])
def api_get_categories():
    # Return the allowed EMAG categories (from the FitnessCategory table)
    categories = FitnessCategory.query.all()
    return jsonify({"categories": [cat.as_dict() for cat in categories]})
