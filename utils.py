"""
Tien ich chung cho vippro campping.
"""

import time
import random


def random_delay(min_sec=1.0, max_sec=3.0):
    """Delay ngau nhien gia hanh vi nguoi that."""
    delay = random.uniform(min_sec, max_sec)
    time.sleep(delay)
    return delay


def clean_customer_id(customer_id):
    """Xoa dau '-' va khoang trang khoi customer ID.

    '123-456-7890' -> '1234567890'
    """
    return str(customer_id).replace("-", "").replace(" ", "").strip()


def format_customer_id(customer_id):
    """Format customer ID thanh dang XXX-XXX-XXXX.

    '1234567890' -> '123-456-7890'
    """
    clean = clean_customer_id(customer_id)
    if len(clean) == 10:
        return f"{clean[:3]}-{clean[3:6]}-{clean[6:]}"
    return clean
