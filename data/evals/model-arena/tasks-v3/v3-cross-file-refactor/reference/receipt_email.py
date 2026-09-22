"""Plain-text receipt email body."""
import fees


def receipt_body(customer, subtotal, rate_bps, minimum_fee=0.0):
    """Receipt text sent to the buyer after a successful charge."""
    fee = fees.compute_fee(subtotal, rate_bps, minimum_fee)
    return (f"Hi {customer},\n\n"
            f"Subtotal: {subtotal:.2f}\n"
            f"Fee: {fee:.2f}\n"
            f"Total: {subtotal + fee:.2f}\n")
