import frappe
from datetime import datetime, timedelta, time

def calculate_weekly_attendance_and_add_salary():
    # Calculate dates dynamically
    # today = datetime(2024, 7, 29)
    today = datetime.now().date()
    # Find the most recent Sunday
    previous_sunday = today - timedelta(days=today.weekday() + 1)
    # Find the last Saturday
    last_saturday = previous_sunday + timedelta(days=7)


    # Get all employees with specific designations
    designations = get_designations()
    employees = frappe.get_all('Employee', filters={'designation': ['in', designations]},
                               fields=['name', 'employee_name', 'ctc'])

    for employee in employees:
        # Get all check-ins for the employee from the previous Sunday to the last Saturday
        checkins = frappe.get_all('Employee Checkin', filters={
            'employee': employee.name,
            'time': ['between', [previous_sunday, last_saturday]]
        }, fields=['time', 'log_type'])

        # Organize check-ins by date
        checkins_by_date = {}
        for checkin in checkins:
            checkin_date = checkin.time.date()
            if checkin_date not in checkins_by_date:
                checkins_by_date[checkin_date] = []
            checkins_by_date[checkin_date].append(checkin)

        attended_days = set()
        
        for checkin_date, checkins in checkins_by_date.items():
            shift_start_time, shift_end_time = get_shift_times(employee.name, checkin_date)
            if shift_start_time and shift_end_time:
                work_time = calculate_day_work_time(checkins, shift_start_time, shift_end_time)
                if work_time > timedelta():
                    attended_days.add(checkin_date)

        # Check if the employee attended all 7 days and worked on Sunday
        if len(attended_days) >= 7 and previous_sunday.date() in attended_days:
            # Calculate daily salary based on the total CTC and work time
            day_salary = (employee.ctc / 6) * (work_time / timedelta(hours=12))  # Assume 12 hours work day
            add_additional_salary_for_full_attendance(employee.name, day_salary, previous_sunday)

    frappe.db.commit()

def get_designations():
    designations = frappe.get_all('Extra Day Allowance Designation', fields=['designation'])
    return [d.designation for d in designations]

def get_shift_times(employee_name, date):
    # Fetch the shift details for the employee on the given date
    shift = frappe.get_value('Employee', employee_name, 'default_shift')
    if shift:
        shift_start_time_td = frappe.get_value('Shift Type', shift, 'start_time')  # Assume this returns timedelta
        shift_end_time_td = frappe.get_value('Shift Type', shift, 'end_time')  # Assume this returns timedelta
        
        shift_start_time = (datetime.min + shift_start_time_td).time()
        shift_end_time = (datetime.min + shift_end_time_td).time()

        return datetime.combine(date, shift_start_time), datetime.combine(date, shift_end_time)
    return None, None

def calculate_day_work_time(checkins, shift_start_time, shift_end_time):
    in_time = None
    out_time = None

    for checkin in checkins:
        if checkin.log_type == 'IN':
            in_time = checkin.time
        elif checkin.log_type == 'OUT':
            out_time = checkin.time

    if in_time and out_time:
        # Calculate actual work time
        if in_time < shift_start_time:
            in_time = shift_start_time
        if out_time > shift_end_time:
            out_time = shift_end_time

        work_duration = out_time - in_time
        return work_duration
    return timedelta()

def add_additional_salary_for_full_attendance(employee_name, amount, payroll_date):
    additional_salary_doc = frappe.new_doc("Additional Salary")
    additional_salary_doc.employee = employee_name
    additional_salary_doc.salary_component = 'Extra Day Allowance'
    additional_salary_doc.amount = amount
    additional_salary_doc.payroll_date = payroll_date
    additional_salary_doc.overwrite_salary_structure_amount = 0
    additional_salary_doc.save()
    additional_salary_doc.submit()
