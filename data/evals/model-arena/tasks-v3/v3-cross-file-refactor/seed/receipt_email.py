"""Plain-text receipt email body."""
import fees


def receipt_body(customer, subtotal, rate):
    """Receipt text sent to the buyer after a successful charge."""
    fee = fees.calc_fee(subtotal, rate)
    return (f"Hi {customer},\n\n"
            f"Subtotal: {subtotal:.2f}\n"
            f"Fee: {fee:.2f}\n"
            f"Total: {subtotal + fee:.2f}\n")
