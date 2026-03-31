from app.db import get_cursor


def get_children(user_id):

    cursor = get_cursor()

    cursor.execute("""
        SELECT id, username
        FROM users
        WHERE sponsor_id = %s
    """, (user_id,))

    children = cursor.fetchall()

    return children

def build_tree(user_id, depth=0, max_depth=10):

    # Stop recursion if max depth reached
    if depth >= max_depth:
        return []

    children = get_children(user_id)

    tree = []

    for child in children:

        node = {
            "user_id": child["id"],
            "username": child["username"],
            "children": build_tree(child["id"], depth + 1, max_depth)
        }

        tree.append(node)

    return tree


def get_user_tree(user_id):

    cursor = get_cursor()

    cursor.execute("""
        SELECT id, username
        FROM users
        WHERE id = %s
    """, (user_id,))

    user = cursor.fetchone()

    if not user:
        return None

    tree = {
        "user_id": user["id"],
        "username": user["username"],
        "children": build_tree(user["id"])
    }

    return tree
