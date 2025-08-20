import random
import string

def generate_4digit_code():
    # numeric 4-digit code, avoids leading zero for readability
    return "{:04d}".format(random.randint(1000, 9999))
