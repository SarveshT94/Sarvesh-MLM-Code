import secrets
import string


def generate_epin():

    alphabet = string.ascii_uppercase + string.digits

    return ''.join(secrets.choice(alphabet) for _ in range(12))
