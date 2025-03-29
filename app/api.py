import threading
from flask import Blueprint, request, jsonify
from app.logger import add_log
from app.services.emag_full_seq import run_create_process, run_update_process

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
