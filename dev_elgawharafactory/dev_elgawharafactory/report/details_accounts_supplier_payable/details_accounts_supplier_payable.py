# Copyright (c) 2024, Omneya Eid and contributors
# For license information, please see license.txt

import frappe
from dev_elgawharafactory.dev_elgawharafactory.report.details_accounts_supplier_payable.details_accounts_supplier_payable_handler import ReceivablePayableReport

def execute(filters=None):
	args = {
		"account_type": "Payable",
		"naming_by": ["Buying Settings", "supp_master_name"],
	}
	return ReceivablePayableReport(filters).run(args)
