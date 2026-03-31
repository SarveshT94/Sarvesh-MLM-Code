from app.db import get_cursor


def create_ticket(user_id, subject, message):

    cursor = get_cursor()

    cursor.execute("""
        INSERT INTO support_tickets (user_id, subject)
        VALUES (%s, %s)
        RETURNING id
    """, (user_id, subject))

    ticket_id = cursor.fetchone()["id"]

    cursor.execute("""
        INSERT INTO ticket_messages
        (ticket_id, sender_id, sender_role, message)
        VALUES (%s, %s, %s, %s)
    """, (
        ticket_id,
        user_id,
        "user",
        message
    ))

    return ticket_id

def reply_ticket(ticket_id, sender_id, role, message):

    cursor = get_cursor()

    cursor.execute("""
        INSERT INTO ticket_messages
        (ticket_id, sender_id, sender_role, message)
        VALUES (%s,%s,%s,%s)
    """, (
        ticket_id,
        sender_id,
        role,
        message
    ))

def get_ticket_messages(ticket_id):

    cursor = get_cursor()

    cursor.execute("""
        SELECT sender_role, message, created_at
        FROM ticket_messages
        WHERE ticket_id = %s
        ORDER BY created_at
    """, (ticket_id,))

    return cursor.fetchall()
