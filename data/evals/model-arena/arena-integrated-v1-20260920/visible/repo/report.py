"""Reporting surface. The visible suite never imports this module."""
import ledger


def weekly_total(entries):
    return ledger.total(entries)
