# -*- coding: utf-8 -*-
"""Shared demo schedule and status distribution rules."""
from datetime import timedelta

PRE_SALE = 1
ON_SALE = 2
SOLD_OUT = 3
ENDED = 4

ENDED_RATIO = 0.45
SOLD_OUT_RATIO = 0.15
ON_SALE_RATIO = 0.10


def bucket_for_index(index, total):
    """Assign sessions to ended / sold-out / on-sale / presale buckets."""
    ended_end = int(total * ENDED_RATIO)
    sold_out_end = int(total * (ENDED_RATIO + SOLD_OUT_RATIO))
    on_sale_end = int(total * (ENDED_RATIO + SOLD_OUT_RATIO + ON_SALE_RATIO))
    if index < ended_end:
        return ENDED
    if index < sold_out_end:
        return SOLD_OUT
    if index < on_sale_end:
        return ON_SALE
    return PRE_SALE


def show_day_for_status(status, today, rng):
    if status == ENDED:
        return today - timedelta(days=rng.randint(1, 90))
    if status in (SOLD_OUT, ON_SALE):
        return today + timedelta(days=rng.randint(1, 20))
    return today + timedelta(days=rng.randint(40, 120))


def sale_start_for(show_time):
    """Use one release window so sale starts preserve show-time ordering."""
    return show_time - timedelta(days=30)
