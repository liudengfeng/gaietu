import string
import random
import re
import uuid


def generate_unique_code(length=32):
    code = uuid.uuid4().hex
    return code[:length]


def is_valid_email(email):
    if email is None or email == "":
        return False
    # 正则表达式匹配电子邮件地址
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def is_valid_phone_number(phone_number):
    if phone_number is None or phone_number == "":
        return False
    # 正则表达式匹配中国大陆手机号码
    pattern = r"^1[3-9]\d{9}$"
    return bool(re.match(pattern, phone_number))


def generate_random_pw(length: int = 16) -> str:
    """
    Generates a random password.

    Parameters
    ----------
    length: int
        The length of the returned password.
    Returns
    -------
    str
        The randomly generated password.
    """
    letters = string.ascii_letters + string.digits
    return "".join(random.choice(letters) for i in range(length)).replace(" ", "")
