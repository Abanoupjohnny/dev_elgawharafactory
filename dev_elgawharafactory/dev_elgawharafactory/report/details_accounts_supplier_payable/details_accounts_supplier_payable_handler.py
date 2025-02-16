from collections import OrderedDict
import frappe
from erpnext.accounts.utils import get_currency_precision, get_party_types_from_account_type
from frappe import _, qb, scrub
from frappe.query_builder import Criterion
from frappe.query_builder.functions import Substring
from frappe.utils import flt, getdate, nowdate


def execute(filters=None):
    args = {"account_type": "Receivable", "naming_by": ["Selling Settings", "cust_master_name"]}
    return ReceivablePayableReport(filters).run(args)


def get_purchase_invoice_items(voucher_no):
    return frappe.get_all("Purchase Invoice Item", filters={"parent": voucher_no},
                          fields=["item_code", "qty", "rate", "amount", "description"])


def get_currency_fields():
    return ["invoiced", "paid", "credit_note", "outstanding", "future_amount", "remaining_balance"]


def allocate_closing_to_term(row, term, key):
    if row[key]:
        if row[key] > term.outstanding:
            term[key] = term.outstanding
            row[key] -= term.outstanding
        else:
            term[key] = row[key]
            row[key] = 0
    term.outstanding -= term[key]


class ReceivablePayableReport:
    def __init__(self, filters=None):
        self.filters = frappe._dict(filters or {})
        self.qb_selection_filter = []
        self.ple = qb.DocType("Payment Ledger Entry")
        self.filters.report_date = getdate(self.filters.report_date or nowdate())
        self.age_as_on = (
            getdate(nowdate()) if self.filters.report_date > getdate(nowdate()) else self.filters.report_date)

    def run(self, args):
        self.filters.update(args)
        self.set_defaults()
        self.party_naming_by = frappe.db.get_value(args.get("naming_by")[0], None, args.get("naming_by")[1])
        self.get_columns()
        self.get_data()
        self.calculate_totals()
        return self.columns, self.data, None, None, None, self.skip_total_row

    def set_defaults(self):
        if not self.filters.get("company"):
            self.filters.company = frappe.db.get_single_value("Global Defaults", "default_company")
        self.company_currency = frappe.get_cached_value("Company", self.filters.get("company"), "default_currency")
        self.currency_precision = get_currency_precision() or 2
        self.dr_or_cr = "debit" if self.filters.account_type == "Receivable" else "credit"
        self.account_type = self.filters.account_type
        self.party_type = get_party_types_from_account_type(self.account_type)
        self.party_details = {}
        self.invoices = set()
        self.skip_total_row = 1

        if self.filters.get("group_by_party"):
            self.previous_party = ""
            self.total_row_map = {}
            self.skip_total_row = 1

        if self.filters.get("in_party_currency"):
            if self.filters.get("party") and len(self.filters.get("party")) == 1:
                self.skip_total_row = 0
            else:
                self.skip_total_row = 1

    def init_voucher_balance(self):
        # build all keys, since we want to exclude vouchers beyond the report date
        for ple in self.ple_entries:
            # get the balance object for voucher_type

            if self.filters.get("ignore_accounts"):
                key = (ple.voucher_type, ple.voucher_no, ple.party)
            else:
                key = (ple.account, ple.voucher_type, ple.voucher_no, ple.party)

            if key not in self.voucher_balance:
                self.voucher_balance[key] = frappe._dict(
                    voucher_type=ple.voucher_type,
                    voucher_no=ple.voucher_no,
                    party=ple.party,
                    party_account=ple.account,
                    posting_date=ple.posting_date,
                    account_currency=ple.account_currency,
                    remarks=ple.remarks,
                    invoiced=0.0,
                    paid=0.0,
                    credit_note=0.0,
                    outstanding=0.0,
                    invoiced_in_account_currency=0.0,
                    paid_in_account_currency=0.0,
                    credit_note_in_account_currency=0.0,
                    outstanding_in_account_currency=0.0,
                    cost_center=ple.cost_center,
                )
            self.get_invoices(ple)

            if self.filters.get("group_by_party"):
                self.init_subtotal_row(ple.party)

        if self.filters.get("group_by_party") and not self.filters.get("in_party_currency"):
            self.init_subtotal_row("Total")

    def get_invoices(self, ple):
        if ple.voucher_type in ("Sales Invoice", "Purchase Invoice"):
            if self.filters.get("sales_person"):
                if ple.voucher_no in self.sales_person_records.get(
                        "Sales Invoice", []
                ) or ple.party in self.sales_person_records.get("Customer", []):
                    self.invoices.add(ple.voucher_no)
            else:
                self.invoices.add(ple.voucher_no)

    def init_subtotal_row(self, party):
        if not self.total_row_map.get(party):
            self.total_row_map.setdefault(party, {"party": party, "bold": 1})

            for field in get_currency_fields():
                self.total_row_map[party][field] = 0.0

    def get_voucher_balance(self, ple):
        if self.filters.get("sales_person"):
            if not (
                    ple.party in self.sales_person_records.get("Customer", [])
                    or ple.against_voucher_no in self.sales_person_records.get("Sales Invoice", [])
            ):
                return

        if self.filters.get("ignore_accounts"):
            key = (ple.against_voucher_type, ple.against_voucher_no, ple.party)
        else:
            key = (ple.account, ple.against_voucher_type, ple.against_voucher_no, ple.party)

        # If payment is made against credit note
        # and credit note is made against a Sales Invoice
        # then consider the payment against original sales invoice.
        if ple.against_voucher_type in ("Sales Invoice", "Purchase Invoice"):
            if ple.against_voucher_no in self.return_entries:
                return_against = self.return_entries.get(ple.against_voucher_no)
                if return_against:
                    if self.filters.get("ignore_accounts"):
                        key = (ple.against_voucher_type, return_against, ple.party)
                    else:
                        key = (ple.account, ple.against_voucher_type, return_against, ple.party)

        row = self.voucher_balance.get(key)

        if not row:
            # no invoice, this is an invoice / stand-alone payment / credit note
            if self.filters.get("ignore_accounts"):
                row = self.voucher_balance.get((ple.voucher_type, ple.voucher_no, ple.party))
            else:
                row = self.voucher_balance.get((ple.account, ple.voucher_type, ple.voucher_no, ple.party))

        row.party_type = ple.party_type
        return row

    def update_voucher_balance(self, ple):
        # get the row where this balance needs to be updated
        # if it's a payment, it will return the linked invoice or will be considered as advance
        row = self.get_voucher_balance(ple)
        if not row:
            return

        if self.filters.get("in_party_currency") or self.filters.get("party_account"):
            amount = ple.amount_in_account_currency
        else:
            amount = ple.amount
        amount_in_account_currency = ple.amount_in_account_currency

        # update voucher
        if ple.amount > 0:
            if (
                    ple.voucher_type in ["Journal Entry", "Payment Entry"]
                    and ple.voucher_no != ple.against_voucher_no
            ):
                row.paid -= amount
                row.paid_in_account_currency -= amount_in_account_currency
            else:
                row.invoiced += amount
                row.invoiced_in_account_currency += amount_in_account_currency
        else:
            if self.is_invoice(ple):
                if row.voucher_no == ple.voucher_no == ple.against_voucher_no:
                    row.paid -= amount
                    row.paid_in_account_currency -= amount_in_account_currency
                else:
                    row.credit_note -= amount
                    row.credit_note_in_account_currency -= amount_in_account_currency
            else:
                row.paid -= amount
                row.paid_in_account_currency -= amount_in_account_currency

    def update_sub_total_row(self, row, party):
        total_row = self.total_row_map.get(party)
        if total_row:
            for field in get_currency_fields():
                total_row[field] += row.get(field, 0.0)
            total_row["currency"] = row.get("currency", "")

    def append_subtotal_row(self, party):
        party_key = tuple(party.items())
        sub_total_row = self.total_row_map.get(party_key)
        if sub_total_row:
            self.data.append(sub_total_row)
            self.data.append({})
            self.update_sub_total_row(sub_total_row, "Total")

    def calculate_totals(self):
        # Initialize a dictionary to hold total amounts for each currency
        self.currency_totals = {}

        # Loop through each row in the data
        for row in self.data:
            # Check if voucher_no is set
            if not row.get("item_code"):  # Adjust the key based on your data structure
                currency = row.get("currency", "Unknown")  # Default to "Unknown" if not present

                # Loop through each currency field you want to total
                for currency_field in get_currency_fields():
                    amount = row.get(currency_field, 0.0)

                    # Ensure the amount is numeric
                    try:
                        amount = float(amount)  # Convert to float
                    except (ValueError, TypeError):
                        amount = 0.0  # If conversion fails, default to 0.0

                    # Initialize total for this currency if it doesn't exist
                    if currency not in self.currency_totals:
                        self.currency_totals[currency] = 0.0

                    # Add the amount to the total for this currency
                    self.currency_totals[currency] += amount

        # Optionally append a total row to your data
        self.append_total_row()

    def append_total_row(self):
        # Create a row for totals and initialize with type
        total_row = {"voucher_no": "<strong>Total</strong>"}

        # Initialize total values for each currency field
        currency_fields = get_currency_fields()
        for field in currency_fields:
            total_row[field] = 0.0  # Start with a numeric zero

        # Loop through each row in the data to calculate cumulative totals
        for row in self.data:
            for field in currency_fields:
                amount = row.get(field, 0.0)

                # Ensure the amount is numeric
                try:
                    amount = float(amount)
                except (ValueError, TypeError):
                    amount = 0.0  # Default to 0.0 if conversion fails

                # Add to the appropriate field total
                total_row[field] += amount

        # Append the total row to the data

        if total_row.get("outstanding") is not None:
            outstanding_value = total_row.get("outstanding")
            total_row["outstanding"] = outstanding_value  # Keep it as a numeric value
            total_row["outstanding_display"] = f"<strong>{outstanding_value:.2f}</strong>"  # For display

        if total_row.get("paid") is not None:
            paid_value = total_row.get("paid")
            total_row["paid"] = paid_value  # Keep it as a numeric value
            total_row["paid_display"] = f"<strong>{paid_value:.2f}</strong>"  # For display

        self.data.append(total_row)

    def append_row(self, row):
        # Set party details and other info before processing items
        self.set_party_details(row)

        # Initialize total quantity, total amount, and total rate
        total_qty = 0
        total_amount = 0
        item_count = 0  # To calculate the average rate later

        # Insert the row for the Purchase Invoice
        if row.voucher_type == "Purchase Invoice":
            row.voucher_type_item = "فاتورة مشتريات"

        elif row.voucher_type == "Payment Entry":
            row.voucher_type_item = "مدفوعات"

        else:
            row.voucher_type_item = row.voucher_type

        self.data.append(row)

        # Insert rows for each item in the Purchase Invoice
        if row.voucher_type == "Purchase Invoice":
            purchase_invoice_items = get_purchase_invoice_items(row.voucher_no)

            for item in purchase_invoice_items:
                # Calculate total qty, amount, and accumulate rate
                total_qty += item.qty
                total_amount += item.amount
                item_count += 1

                item_row = frappe._dict({
                    "voucher_no": "",
                    "party": "",
                    "posting_date": "",
                    "item_code": item.item_code,
                    "qty": item.qty,
                    "rate": item.rate,
                    "amount": item.amount
                })

                # Append each item row after the Purchase Invoice row
                self.data.append(item_row)


            # Update the row with total quantities, total amounts, and average rate
            row.qty = total_qty
            row.amount = total_amount
            

        # Update subtotals if needed based on grouping by party
        if self.filters.get("group_by_party"):
            self.update_sub_total_row(row, row.party)
            if self.previous_party and (self.previous_party != row.party):
                self.append_subtotal_row(self.previous_party)
            self.previous_party = row

    def set_invoice_details(self, row):
        invoice_details = self.invoice_details.get(row.voucher_no, {})
        row.update(invoice_details)

        if row.voucher_type == "Sales Invoice":
            if self.filters.show_delivery_notes:
                self.set_delivery_notes(row)

            if self.filters.show_sales_person and row.sales_team:
                row.sales_person = ", ".join(row.sales_team)
                del row["sales_team"]

    def set_delivery_notes(self, row):
        delivery_notes = self.delivery_notes.get(row.voucher_no, [])
        if delivery_notes:
            row.delivery_notes = ", ".join(delivery_notes)

    def build_delivery_note_map(self):
        if self.invoices and self.filters.show_delivery_notes:
            self.delivery_notes = frappe._dict()

            # delivery note link inside sales invoice
            si_against_dn = frappe.db.sql("""select parent, delivery_note
                from `tabSales Invoice Item`
                where docstatus=1 and parent in (%s)""" % (",".join(["%s"] * len(self.invoices))), tuple(self.invoices),
                                          as_dict=1)

            for d in si_against_dn:
                if d.delivery_note:
                    self.delivery_notes.setdefault(d.parent, set()).add(d.delivery_note)

            dn_against_si = frappe.db.sql("""select distinct parent, against_sales_invoice
                from `tabDelivery Note Item`
                where against_sales_invoice in (%s)""" % (",".join(["%s"] * len(self.invoices))), tuple(self.invoices),
                                          as_dict=1)

            for d in dn_against_si:
                self.delivery_notes.setdefault(d.against_sales_invoice, set()).add(d.parent)

    def get_invoice_details(self):
        self.invoice_details = frappe._dict()
        if self.account_type == "Receivable":
            si_list = frappe.db.sql("""select name, due_date, po_no
                from `tabSales Invoice`
                where posting_date <= %s""", self.filters.report_date, as_dict=1)
            for d in si_list:
                self.invoice_details.setdefault(d.name, d)

            # Get Sales Team
            if self.filters.show_sales_person:
                sales_team = frappe.db.sql("""
                    select parent, sales_person
                    from `tabSales Team`
                    where parenttype = 'Sales Invoice'""", as_dict=1)
                for d in sales_team:
                    self.invoice_details.setdefault(d.parent, {}).setdefault("sales_team", []).append(d.sales_person)

    def set_party_details(self, row):
        # customer / supplier name
        party_details = self.get_party_details(row.party) or {}
        row.update(party_details)

        if self.filters.get("in_party_currency") or self.filters.get("party_account"):
            row.currency = row.account_currency
        else:
            row.currency = self.company_currency

    def get_payment_terms(self, row):
        # build payment_terms for row
        payment_terms_details = frappe.db.sql(f"""select
                si.name, si.party_account_currency, si.currency, si.conversion_rate,
                si.total_advance, ps.due_date, ps.payment_term, ps.payment_amount, ps.base_payment_amount,
                ps.description, ps.paid_amount, ps.discounted_amount
            from `tab{row.voucher_type}` si, `tabPayment Schedule` ps
            where si.name = ps.parent and si.name = %s
            order by ps.paid_amount desc, due_date
        """, row.voucher_no, as_dict=1)

        original_row = frappe._dict(row)
        row.payment_terms = []

        # Cr Note's don't have Payment Terms
        if not payment_terms_details:
            return

        # Advance allocated during invoicing is not considered in payment terms
        # Deduct that from paid amount pre allocation
        row.paid -= flt(payment_terms_details[0].total_advance)

        # If single payment terms, no need to split the row
        if len(payment_terms_details) == 1 and payment_terms_details[0].payment_term:
            self.append_payment_term(row, payment_terms_details[0], original_row)
            return

        for d in payment_terms_details:
            term = frappe._dict(original_row)
            self.append_payment_term(row, d, term)

    def append_payment_term(self, row, d, term):
        if (
                self.filters.get("customer") or self.filters.get("supplier")
        ) and d.currency == d.party_account_currency:
            invoiced = d.payment_amount
        else:
            invoiced = d.base_payment_amount

        row.payment_terms.append(term.update({
            "due_date": d.due_date,
            "invoiced": invoiced,
            "invoice_grand_total": row.invoiced,
            "payment_term": d.description or d.payment_term,
            "paid": d.paid_amount + d.discounted_amount,
            "credit_note": 0.0,
            "outstanding": invoiced - d.paid_amount - d.discounted_amount,
        }))

        if d.paid_amount:
            row["paid"] -= d.paid_amount + d.discounted_amount

    def allocate_extra_payments_or_credits(self, row):
        # allocate extra payments / credits
        additional_row = None
        for key in ("paid", "credit_note"):
            if row[key] > 0:
                if not additional_row:
                    additional_row = frappe._dict(row)
                additional_row.invoiced = 0.0
                additional_row[key] = row[key]

        if additional_row:
            additional_row.outstanding = (additional_row.invoiced - additional_row.paid - additional_row.credit_note)
            self.append_row(additional_row)

    def get_return_entries(self):
        doctype = "Sales Invoice" if self.account_type == "Receivable" else "Purchase Invoice"
        filters = {
            "is_return": 1,
            "docstatus": 1,
            "company": self.filters.company,
            "update_outstanding_for_self": 0,
        }
        or_filters = {}
        for party_type in self.party_type:
            party_field = scrub(party_type)
            if self.filters.get(party_field):
                or_filters.update({party_field: self.filters.get(party_field)})
        self.return_entries = frappe._dict(
            frappe.get_all(doctype, filters=filters, or_filters=or_filters, fields=["name", "return_against"],
                           as_list=1))

    def get_ple_entries(self):
        # get all the GL entries filtered by the given filters
        self.prepare_conditions()
        self.qb_selection_filter.append(self.ple.posting_date.lte(self.filters.report_date))

        ple = qb.DocType("Payment Ledger Entry")
        query = (qb.from_(ple).select(
            ple.name, ple.account, ple.voucher_type, ple.voucher_no, ple.against_voucher_type,
            ple.against_voucher_no, ple.party_type, ple.cost_center, ple.party, ple.posting_date,
            ple.due_date, ple.account_currency, ple.amount, ple.amount_in_account_currency,
        ).where(ple.delinked == 0).where(Criterion.all(self.qb_selection_filter)).where(
            Criterion.any(self.or_filters)))

        if self.filters.get("show_remarks"):
            if remarks_length := frappe.db.get_single_value("Accounts Settings", "receivable_payable_remarks_length"):
                query = query.select(Substring(ple.remarks, 1, remarks_length).as_("remarks"))
            else:
                query = query.select(ple.remarks)

        if self.filters.get("group_by_party"):
            query = query.orderby(self.ple.party, self.ple.posting_date)
        else:
            query = query.orderby(self.ple.posting_date, self.ple.party)

        self.ple_entries = query.run(as_dict=True)

    def get_sales_invoices_or_customers_based_on_sales_person(self):
        if self.filters.get("sales_person"):
            lft, rgt = frappe.db.get_value("Sales Person", self.filters.get("sales_person"), ["lft", "rgt"])
            records = frappe.db.sql("""
                select distinct parent, parenttype from `tabSales Team` steam
                where parenttype in ('Customer', 'Sales Invoice')
                    and exists(select name from `tabSales Person` where lft >= %s and rgt <= %s and name = steam.sales_person)
            """, (lft, rgt), as_dict=1)

            self.sales_person_records = frappe._dict()
            for d in records:
                self.sales_person_records.setdefault(d.parenttype, set()).add(d.parent)

    def prepare_conditions(self):
        self.qb_selection_filter = []
        self.or_filters = []

        for _party_type in self.party_type:
            self.add_common_filters()

    def add_common_filters(self):
        if self.filters.company:
            self.qb_selection_filter.append(self.ple.company == self.filters.company)

        if self.filters.finance_book:
            self.qb_selection_filter.append(self.ple.finance_book == self.filters.finance_book)

        if self.filters.get("party_type"):
            self.qb_selection_filter.append(self.filters.party_type == self.ple.party_type)

        if self.filters.get("party"):
            self.qb_selection_filter.append(self.ple.party.isin(self.filters.party))

        if self.filters.party_account:
            self.qb_selection_filter.append(self.ple.account == self.filters.party_account)
        else:
            # get GL with "receivable" or "payable" account_type
            accounts = [d.name for d in frappe.get_all("Account", filters={"account_type": self.account_type,
                                                                           "company": self.filters.company})]

            if accounts:
                self.qb_selection_filter.append(self.ple.account.isin(accounts))

    def is_invoice(self, ple):
        if ple.voucher_type in ("Sales Invoice", "Purchase Invoice"):
            return True

    def get_party_details(self, party):
        if party not in self.party_details:
            self.party_details[party] = frappe.db.get_value("Supplier", party, ["supplier_name", "supplier_group"],
                                                            as_dict=True)

        return self.party_details[party]

    def get_columns(self):
        self.columns = []
        self.add_column("التاريخ", field_type="Date",field_name="posting_date")
        self.add_column(label="Party Type", field_name="party_type", field_type="Data", width=100)
        self.add_column(label="اسم العميل", field_name="party", field_type="Dynamic Link", options="party_type", width=180)
        self.add_column(label=self.account_type + " Account", field_name="party_account", field_type="Link",
                        options="Account", width=180)
        if self.party_naming_by == "Naming Series":
            if self.account_type == "Payable":
                label = "اسم العميل"
                fieldname = "supplier_name"
            else:
                label = "اسم العميل"
                fieldname = "customer_name"
            self.add_column(label=label, field_name=fieldname, field_type="Data")

        self.add_column(label=_("نوع القسيمة"), field_name="voucher_type_item", field_type="Data")
        self.add_column(label=_("رقم القسيمة"), field_name="voucher_no", field_type="Dynamic Link",
                        options="voucher_type", width=180)

        # Adding columns for item details
        self.add_column(label=_("اسم السلعه"), field_name="item_code", field_type="Data", width=120)
        self.add_column(label=_("عدد"), field_name="qty", field_type="Int", width=100)
        self.add_column(label=_("سعر السلعه مفرده"), field_name="rate", field_type="Currency", width=100)
        self.add_column(label=_("اجمالي سعر السلعه"), field_name="amount", field_type="Currency", width=100)

        self.add_column(label=_("مدفوع"), field_name="paid", field_type="Currency", width=100)
        self.add_column(label=_("اجمالي"), field_name="outstanding", field_type="Currency", width=100)

        if self.filters.show_remarks:
            self.add_column(label=_("ملاحظات"), field_name="remarks", field_type="Text", width=200)

    def add_column(self, label, field_name=None, field_type="Currency", options=None, width=120):
        if not field_name:
            field_name = scrub(label)
        if field_type == "Currency":
            options = "currency"
        if field_type == "Date":
            width = 90

        self.columns.append(dict(label=label, fieldname=field_name, fieldtype=field_type, options=options, width=width))

    def get_exchange_rate_revaluations(self):
        je = qb.DocType("Journal Entry")
        results = (qb.from_(je).select(je.name).where(
            (je.company == self.filters.company) & (je.posting_date.lte(self.filters.report_date))
            & ((je.voucher_type == "Exchange Rate Revaluation") | (je.voucher_type == "Exchange Gain Or Loss"))).run())
        self.err_journals = [x[0] for x in results] if results else []

    def get_data(self):
        self.get_ple_entries()
        self.get_sales_invoices_or_customers_based_on_sales_person()
        self.voucher_balance = OrderedDict()
        self.init_voucher_balance()  # invoiced, paid, credit_note, outstanding

        # Build delivery note map against all sales invoices
        self.build_delivery_note_map()

        # Get invoice details like bill_no, due_date etc for all invoices
        self.get_invoice_details()

        # Get return entries
        self.get_return_entries()

        # Get Exchange Rate Revaluations
        self.get_exchange_rate_revaluations()

        self.data = []

        for ple in self.ple_entries:
            self.update_voucher_balance(ple)

        self.build_data()

    def build_data(self):
        # set outstanding for all the accumulated balances
        # as we can use this to filter out invoices without outstanding
        for _key, row in self.voucher_balance.items():
            row.outstanding = flt(row.invoiced - row.paid - row.credit_note, self.currency_precision)
            row.outstanding_in_account_currency = flt(
                row.invoiced_in_account_currency
                - row.paid_in_account_currency
                - row.credit_note_in_account_currency,
                self.currency_precision,
            )

            row.invoice_grand_total = row.invoiced

            must_consider = False
            if self.filters.get("for_revaluation_journals"):
                if (abs(row.outstanding) >= 0.0 / 10 ** self.currency_precision) or (
                        abs(row.outstanding_in_account_currency) >= 0.0 / 10 ** self.currency_precision
                ):
                    must_consider = True
            else:
                if (abs(row.outstanding) >= 1.0 / 10 ** self.currency_precision) and (
                        (abs(row.outstanding_in_account_currency) >= 1.0 / 10 ** self.currency_precision)
                        or (row.voucher_no in self.err_journals)
                ):
                    must_consider = True

            if must_consider:
                # non-zero outstanding, we must consider this row
                self.append_row(row)

        if self.filters.get("group_by_party"):
            self.append_subtotal_row(self.previous_party)
            if self.data:
                self.data.append(self.total_row_map.get("Total", {}))
