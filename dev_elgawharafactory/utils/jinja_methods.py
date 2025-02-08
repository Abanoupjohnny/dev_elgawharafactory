import frappe
from frappe.query_builder import DocType
from frappe.utils import flt
from pypika.functions import Coalesce, Sum

def get_total_outstanding_amount(party):
    ple = DocType("Payment Ledger Entry")

    # Build the query to sum the amount where the party matches
    total_amount = (
        frappe.qb.from_(ple)
        .where(ple.party == party)
        .select(Sum(ple.amount).as_("total_outstanding"))
    ).run()

    # Return the total amount, handling None (in case no rows were found), with 2 decimal precision
    return flt(total_amount[0][0], precision=2) if total_amount else 0.0
