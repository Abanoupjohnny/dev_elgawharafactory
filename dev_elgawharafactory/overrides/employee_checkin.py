from datetime import datetime, timedelta
import frappe
from frappe.utils import getdate
from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin


class CustomEmployeeCheckin(EmployeeCheckin):
    def validate(self):
        # Call the parent class's validate method
        super().validate()
        # Add your custom validation logic here
        self.custom_validation()

    def custom_validation(self):
        apply_penalty(self)

def apply_penalty(doc):
    if doc.is_new():
        if doc.log_type.lower() == "in":
            apply_late_entry_penalty(doc)
        else:
            employee_daily_salary(doc)
            apply_overtime_policy(doc)

def apply_late_entry_penalty(doc):
    employee = frappe.get_doc('Employee', doc.employee)
    designation = employee.designation
    branch = employee.branch

    deduction_min = get_employee_deduction_min(doc, designation, branch)

    if deduction_min > 0:
        ctc = employee.ctc  # Weekly CTC
        deduction_amount = get_employee_deduction_amount(ctc, deduction_min)
        apply_additional_salary(employee=employee.name, amount=deduction_amount,
                                payroll_date=getdate(doc.get("time")),
                                salary_component='Late Entry Penalty')

def apply_overtime_policy(doc):
    extra_minutes = calculate_overtime_minutes(doc)
    if extra_minutes:
        employee_doc = frappe.get_doc("Employee", doc.employee)
        ctc = employee_doc.ctc

        overtime_policy = get_employee_overtime_policy(doc, employee_doc)
        if overtime_policy:
            overtime_multiplier = overtime_policy.extra_time_per
            extra_pay = calculate_extra_pay(ctc, extra_minutes, overtime_multiplier)
            apply_additional_salary(employee=doc.employee, amount=extra_pay,
                                    payroll_date=getdate(doc.get("time")),
                                    salary_component='Over Time')

def get_employee_deduction_min(doc, designation, branch):
    check_in_time_str = str(doc.get("time"))
    check_in_time = datetime.strptime(check_in_time_str, '%Y-%m-%d %H:%M:%S')

    late_entry_penalty = frappe.get_single('Employee Penalty')
    deduction_min = 0

    for penalty in late_entry_penalty.employee_penalties:
        if penalty.designation == designation and penalty.branch == branch:
            from_time = parse_penalty_time(penalty.get("from"))
            to_time = parse_penalty_time(penalty.get("to"))

            if from_time <= check_in_time.time() <= to_time:
                deduction_min = penalty.deduction
                break

    return deduction_min

def parse_penalty_time(time_value):
    if isinstance(time_value, timedelta):
        total_seconds = int(time_value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return datetime.strptime(f"{hours:02}:{minutes:02}:{seconds:02}", '%H:%M:%S').time()
    elif isinstance(time_value, str):
        return datetime.strptime(time_value, '%H:%M:%S').time()
    else:
        raise ValueError("Invalid time value")

def get_employee_deduction_amount(ctc, deduction_min):
    days_per_week = 6
    hours_per_day = 12
    minutes_per_hour = 60
    total_working_minutes_per_week = days_per_week * hours_per_day * minutes_per_hour

    per_minute_wage = ctc / total_working_minutes_per_week
    deduction_amount = per_minute_wage * deduction_min

    return deduction_amount

def calculate_overtime_minutes(doc):
    employee_shift = frappe.db.get_value("Employee", doc.employee, "default_shift")
    shift_end_str = str(frappe.db.get_value("Shift Type", employee_shift, "end_time"))
    shift_end = datetime.strptime(shift_end_str, '%H:%M:%S').time()
    actual_end = datetime.strptime(str(doc.get("time")), '%Y-%m-%d %H:%M:%S').time()

    actual_end_delta = timedelta(hours=actual_end.hour, minutes=actual_end.minute, seconds=actual_end.second)
    shift_end_delta = timedelta(hours=shift_end.hour, minutes=shift_end.minute, seconds=shift_end.second)

    overtime = actual_end_delta - shift_end_delta if actual_end_delta > shift_end_delta else timedelta(0)
    overtime_minutes = overtime.total_seconds() / 60

    return overtime_minutes

def calculate_extra_pay(weekly_salary, extra_minutes, overtime_multiplier):
    daily_hours = 12
    working_days_per_week = 6
    daily_salary = weekly_salary / working_days_per_week
    hourly_rate = daily_salary / daily_hours
    rate_per_minute = hourly_rate / 60
    overtime_rate_per_minute = rate_per_minute * overtime_multiplier
    total_extra_pay = overtime_rate_per_minute * extra_minutes

    return round(total_extra_pay, 2)

def get_employee_overtime_policy(doc, employee_doc):
    employee_penalty_doc = frappe.get_single("Employee Penalty")
    overtime_policy = None

    for policy in employee_penalty_doc.overtime_policy:
        if (policy.active and
                policy.designation == employee_doc.designation and
                policy.branch == employee_doc.branch and
                policy.shift_type == employee_doc.default_shift):
            overtime_policy = policy
            break

    return overtime_policy


def employee_daily_salary(doc):
    check_out = str(doc.get("time"))
    employee = doc.get("employee")
    
    # Fetch the shift type end time
    shift_type_end_time = get_shift_type_end_time(employee)
    
    check_in = frappe.db.sql("""
        SELECT time FROM `tabEmployee Checkin`
        WHERE employee = %s AND time < %s
        ORDER BY time DESC LIMIT 1
    """, (employee, check_out), as_dict=True)
    
    if not check_in:
        frappe.throw(_("No check-in record found for the employee before the check-out time."))
    
    check_in = check_in[0].time.strftime('%Y-%m-%d %H:%M:%S')
    total_weekly_pay = frappe.db.get_value("Employee", employee, "ctc")
    expected_weekly_hours = 72  # 6 days * 12 hours

    # Use the shift type end time if the check-out is after the end time
    check_out = min(check_out, shift_type_end_time.strftime('%Y-%m-%d %H:%M:%S'))

    daily_work_duration = calculate_work_time(check_in, check_out)
    
    daily_payment = calculate_daily_payment(
        total_weekly_pay, 
        expected_weekly_hours, 
        daily_work_duration.total_seconds()
    )
    
    apply_additional_salary(employee=employee, amount=daily_payment, payroll_date=getdate(doc.get("time")), salary_component="Daily Salary")

def get_shift_type_end_time(employee):
    # Replace this with the logic to get the actual shift type end time for the employee
    shift_type = frappe.db.get_value("Employee", employee, "default_shift")
    shift_end_time = str(frappe.db.get_value("Shift Type", shift_type, "end_time"))
    shift_end_time = datetime.strptime(shift_end_time, '%H:%M:%S').time()
    return datetime.combine(datetime.today(), shift_end_time)


def calculate_work_time(check_in, check_out):
    fmt = '%Y-%m-%d %H:%M:%S'
    check_in_time = datetime.strptime(check_in, fmt)
    check_out_time = datetime.strptime(check_out, fmt)
    work_duration = check_out_time - check_in_time
    return work_duration

def calculate_daily_payment(total_weekly_pay, expected_weekly_hours, work_duration_seconds):
    daily_pay = (total_weekly_pay / (expected_weekly_hours * 3600)) * work_duration_seconds
    return daily_pay


def apply_additional_salary(employee, amount, payroll_date, salary_component):
    additional_salary_doc = frappe.new_doc("Additional Salary")
    additional_salary_doc.employee = employee
    additional_salary_doc.salary_component = salary_component
    additional_salary_doc.amount = amount
    additional_salary_doc.payroll_date = payroll_date
    additional_salary_doc.overwrite_salary_structure_amount = 0
    additional_salary_doc.save()
    additional_salary_doc.submit()
