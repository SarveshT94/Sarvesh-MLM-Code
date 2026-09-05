"""
app/routes/team_routes.py  —  NEW FILE

Drill-down team API. The "My Team" screen calls the SAME endpoint with the
currently selected member's id, so the audit/ drill follows the selection:

    GET /api/team/node                -> logged-in user's own root node
    GET /api/team/node?user_id=123    -> any member (admin only for other ids)
    GET /api/team/node/123            -> same, path style

Query params: page, page_size, rank, level (reserved), status (active|inactive)

Response:
    { node:{...}, stats:{total_team, direct_referrals, active, rank},
      level:1, children:[...], pagination:{page,pages,total} }

Only ONE level of children is returned per call; each child carries
total_team_count + direct_count, so the browser fetches deeper on click.
That is what keeps it instant with 100k+ users.
"""
from __future__ import annotations

import logging

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user

from app.services.team_service import (
    get_team_node,
    get_total_team_count,
    get_level_1_team,
    get_user_network_profile,
)
from app.services.sponsor_service import get_sponsor_chain

logger = logging.getLogger(__name__)
team_bp = Blueprint("team", __name__)


def _is_admin() -> bool:
    return getattr(current_user, "role_id", None) == 1


def _resolve_target_id():
    """Members can only view their own subtree; admins may view anyone."""
    target = request.args.get("user_id", type=int)
    if target and target != int(current_user.id) and not _is_admin():
        return None  # not allowed
    return target or int(current_user.id)


@team_bp.route("/team/node", methods=["GET"])
@team_bp.route("/team/node/<int:user_id>", methods=["GET"])
@login_required
def team_node(user_id=None):
    target = user_id or _resolve_target_id()
    if target is None:
        return jsonify({"success": False, "message": "Not authorized"}), 403

    try:
        data = get_team_node(
            target,
            viewer_id=current_user.id,
            page=request.args.get("page", 1, type=int),
            page_size=request.args.get("page_size", 12, type=int),
            rank=request.args.get("rank"),
            status=request.args.get("status"),
        )
        if not data:
            return jsonify({"success": False, "message": "Member not found"}), 404

        # Admin drill: include the breadcrumb upline so the UI can show
        # YOU > Sponsor > ... > selected member.
        data["breadcrumb"] = []
        if _is_admin() and target != int(current_user.id):
            data["breadcrumb"] = get_sponsor_chain(target)[::-1]

        return jsonify({"success": True, "data": data}), 200
    except Exception as e:
        logger.error("team_node error: %s", e)
        return jsonify({"success": False, "message": "Failed to load team"}), 500


@team_bp.route("/team/summary", methods=["GET"])
@login_required
def team_summary():
    """Lightweight header counters for the logged-in user."""
    uid = int(current_user.id)
    try:
        return jsonify({
            "success": True,
            "data": {
                "total_team": get_total_team_count(uid),
                "direct_referrals": len(get_level_1_team(uid)),
            },
        }), 200
    except Exception as e:
        logger.error("team_summary error: %s", e)
        return jsonify({"success": False, "message": "Failed"}), 500


@team_bp.route("/team/network/<int:user_id>", methods=["GET"])
@login_required
def team_network(user_id):
    if not _is_admin():
        return jsonify({"success": False, "message": "Not authorized"}), 403
    try:
        return jsonify({"success": True, "data": get_user_network_profile(user_id)}), 200
    except Exception as e:
        logger.error("team_network error: %s", e)
        return jsonify({"success": False, "message": "Failed"}), 500
