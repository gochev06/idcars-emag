from flask import Blueprint, request, jsonify
from app.extensions import scheduler  # Import scheduler from extensions
from app.services.emag_full_seq import (
    run_update_process,
)
from flask_apscheduler.utils import job_to_dict

sched_bp = Blueprint("sched", __name__)


def update_job():
    run_update_process(pause=1, batch_size=50)


@sched_bp.route("/schedule", methods=["POST"])
def schedule_update():
    data = request.get_json() or {}
    schedule_type = data.get("schedule_type")
    job_id = "update_job"
    existing = scheduler.get_job(job_id)
    if existing:
        scheduler.remove_job(job_id)

    if schedule_type == "time":
        time_str = data.get("time")
        if not time_str:
            return jsonify({"status": "error", "message": "Time not provided"}), 400
        hour, minute = map(int, time_str.split(":"))
        scheduler.add_job(
            func=update_job,
            trigger="cron",
            id=job_id,
            hour=hour,
            minute=minute,
            replace_existing=True,
        )
    elif schedule_type == "interval":
        interval_hours = data.get("interval_hours")
        if not interval_hours:
            return (
                jsonify({"status": "error", "message": "Interval hours not provided"}),
                400,
            )
        scheduler.add_job(
            func=update_job,
            trigger="interval",
            id=job_id,
            hours=interval_hours,
            replace_existing=True,
        )
    else:
        return jsonify({"status": "error", "message": "Invalid schedule type"}), 400

    return jsonify(
        {"status": "success", "message": "Update job scheduled", "job_id": job_id}
    )


@sched_bp.route("/job", methods=["GET"])
def get_job():
    job_id = "update_job"
    job = scheduler.get_job(job_id)
    if job:
        return jsonify({"status": "success", "job": job_to_dict(job)})
    else:
        return jsonify({"status": "error", "message": "No scheduled job found"}), 404


@sched_bp.route("/cancel", methods=["DELETE"])
def cancel_job():
    job_id = "update_job"
    job = scheduler.get_job(job_id)
    if job:
        scheduler.remove_job(job_id)
        return jsonify({"status": "success", "message": "Job canceled"})
    else:
        return jsonify({"status": "error", "message": "No job found to cancel"}), 404


@sched_bp.route("/trigger", methods=["POST"])
def trigger_update():
    try:
        update_job()
        return jsonify(
            {"status": "success", "message": "Update process triggered manually"}
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
