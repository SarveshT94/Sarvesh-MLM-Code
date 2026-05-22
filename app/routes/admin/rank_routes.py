from flask import Blueprint, request, jsonify
from app.db import get_cursor
from app.utils.auth import admin_required

rank_bp = Blueprint('admin_ranks', __name__, url_prefix='/admin/api/ranks')

@rank_bp.route('/', methods=['GET'])
@admin_required
def get_rank_rules():
    """Fetch all rank rules so Admin can view them on the frontend."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM rank_rules ORDER BY level ASC")
            rules = cur.fetchall()
        return jsonify({"status": "success", "data": rules})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400

@rank_bp.route('/<int:level>', methods=['PUT'])
@admin_required
def update_rank_rule(level):
    """Update team size, volume requirements, or bonus percentages from the Admin Panel."""
    data = request.json
    try:
        with get_cursor() as cur:
            cur.execute("""
                UPDATE rank_rules 
                SET rank_name = %s, req_team_size = %s, req_business_vol = %s, bonus_percentage = %s
                WHERE level = %s
            """, (
                data.get('rank_name'),
                data.get('req_team_size'),
                data.get('req_business_vol'),
                data.get('bonus_percentage'),
                level
            ))
        return jsonify({"status": "success", "message": f"Level {level} rules updated successfully."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 400
