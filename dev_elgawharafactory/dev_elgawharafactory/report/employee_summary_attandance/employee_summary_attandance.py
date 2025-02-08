import frappe
from datetime import datetime, timedelta

def execute(filters=None):
    try:
        columns = get_columns()
        filters = frappe._dict(filters)
        week_start, week_end = get_week_range(filters)
        data = get_data(filters, week_start, week_end)
        return columns, data
    except ImportError as e:
        frappe.throw(f"Import Error: {str(e)}")
    except Exception as e:
        frappe.throw(f"An error occurred: {str(e)}")



def get_data(filters, week_start, week_end):
    try:
        conditions = get_conditions(filters, week_start, week_end)
        query = f"""
        SELECT
            emp.name AS `Employee ID`,
            emp.designation AS `Designation`,
            emp.branch AS `Branch`,
            chk.time AS `Checkin Time`,
            chk.log_type AS `Log Type`
        FROM
            `tabEmployee Checkin` chk
        JOIN
            `tabEmployee` emp ON chk.employee = emp.name
        LEFT JOIN
            `tabShift Type` shift ON shift.name = emp.default_shift
        {conditions}
        ORDER BY
            emp.name, chk.time
        """
        
        data = frappe.db.sql(query, filters, as_dict=1)

        weekly_totals = {}
        weekly_attendance = {}

        for row in data:
            employee_id = row['Employee ID']
            designation = row['Designation']
            branch = row['Branch']
            shift_type = frappe.get_value("Employee", employee_id, "default_shift")
            shift_details = frappe.get_doc("Shift Type", shift_type)
            shift_start_time = shift_details.start_time
            shift_end_time = shift_details.end_time

            if isinstance(shift_start_time, timedelta):
                shift_start_time = convert_timedelta_to_time(shift_start_time)
            if isinstance(shift_end_time, timedelta):
                shift_end_time = convert_timedelta_to_time(shift_end_time)

            if employee_id not in weekly_totals:
                weekly_totals[employee_id] = {
                    'Total Hours': timedelta(0),
                    'Overtime Hours': timedelta(0),
                    'Non-Ot Hours': timedelta(0),
                    'Daily Checkins': {},
                    'Days Attended': 0,
                    'Designation': designation,
                    'Branch': branch,
                    'Attendance Week': week_start.isocalendar()[1]  # Add week number here
                }
                weekly_attendance[employee_id] = set()

            checkin_date = row['Checkin Time'].date()

            if row['Log Type'] == 'IN':
                if row['Checkin Time'].time() < shift_start_time:
                    row['Checkin Time'] = datetime.combine(checkin_date, shift_start_time)
                
                if checkin_date not in weekly_totals[employee_id]['Daily Checkins']:
                    weekly_totals[employee_id]['Daily Checkins'][checkin_date] = {'in': None, 'out': None}
                
                weekly_totals[employee_id]['Daily Checkins'][checkin_date]['in'] = row['Checkin Time']
                weekly_attendance[employee_id].add(checkin_date)

            elif row['Log Type'] == 'OUT':
                if checkin_date not in weekly_totals[employee_id]['Daily Checkins']:
                    continue  # Skip if there was no corresponding check-in

                weekly_totals[employee_id]['Daily Checkins'][checkin_date]['out'] = row['Checkin Time']

        result_data = []

        for employee_id, totals in weekly_totals.items():
            days_attended = len(weekly_attendance.get(employee_id, set()))
            days_absent = (week_end - week_start).days + 1 - days_attended

            for checkin_date, times in totals['Daily Checkins'].items():
                if times['in'] and times['out']:
                    checkin_datetime = times['in']
                    checkout_datetime = times['out']

                    total_hours = checkout_datetime - checkin_datetime
                    overtime_hours = max(timedelta(0), checkout_datetime - datetime.combine(checkin_date, shift_end_time))
                    non_overtime_hours = total_hours - overtime_hours

                    weekly_totals[employee_id]['Total Hours'] += total_hours
                    weekly_totals[employee_id]['Overtime Hours'] += overtime_hours
                    weekly_totals[employee_id]['Non-Ot Hours'] += non_overtime_hours

            # Fetch additional salary for the employee
            additional_salary = get_additional_salary(employee_id, week_start, week_end)

            row = {
                'Employee ID': employee_id,
                'Designation': totals['Designation'],
                'Branch': totals['Branch'],
                'Total Hours': format_timedelta(totals['Total Hours']),
                'Overtime Hours': format_timedelta(totals['Overtime Hours']),
                'Non-Ot Hours': format_timedelta(totals['Non-Ot Hours']),
                'Days Attended': days_attended,
                'Days Absent': days_absent,
                'Shift Type': shift_type,
                'Deductions': additional_salary.get('Deductions', 0),
                'Earnings': additional_salary.get('Earnings', 0),
                'Net Earnings': additional_salary.get('Earnings', 0) - additional_salary.get('Deductions', 0),
                'Week Start': week_start,
                'Week End': week_end,
                'Attendance Week': totals['Attendance Week']  # Include week number here
            }
            result_data.append(row)

        return result_data
    except Exception as e:
        frappe.throw(f"An error occurred while fetching data: {str(e)}")


def convert_timedelta_to_time(td):
    return (datetime.min + td).time()

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

def get_conditions(filters, week_start, week_end):
    conditions = []

    if filters.get('employee'):
        conditions.append("chk.employee = %(employee)s")
    if filters.get('designation'):
        conditions.append("emp.designation = %(designation)s")
    if filters.get('branch'):
        conditions.append("emp.branch = %(branch)s")
    if filters.get('from_date') and filters.get('to_date'):
        conditions.append("DATE(chk.time) BETWEEN %(from_date)s AND %(to_date)s")

    if conditions:
        return "WHERE " + " AND ".join(conditions)
    else:
        return ""

def get_week_range(filters):
    today = datetime.today().date()
    if filters.get('from_date') and filters.get('to_date'):
        week_start = filters.get('from_date')
        week_end = filters.get('to_date')
    else:
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

    return week_start, week_end

def get_week_start_date(week):
    today = datetime.today().date()
    year, week_num, _ = today.isocalendar()
    return datetime.fromisocalendar(year, week, 1).date()


def get_columns():
    return [
        {"label": "اسم الموظف", "fieldname": "Employee ID", "fieldtype": "Link", "options": "Employee", "width": 150},
        {"label": "المسمى الوظيفي", "fieldname": "Designation", "fieldtype": "Link", "options": "Designation", "width": 120},
        {"label": "الفرع", "fieldname": "Branch", "fieldtype": "Link", "options": "Branch", "width": 120},
        {"label": "نوع الشيفت", "fieldname": "Shift Type", "fieldtype": "Link", "options": "Shift Type", "width": 100},
        {"label": "أسبوع الحضور", "fieldname": "Attendance Week", "fieldtype": "Data", "width": 120},
        {"label": "بداية الأسبوع", "fieldname": "Week Start", "fieldtype": "Date", "width": 120},
        {"label": "نهاية الأسبوع", "fieldname": "Week End", "fieldtype": "Date", "width": 120},
        {"label": "اجمالي عدد الساعات", "fieldname": "Total Hours", "fieldtype": "Data", "width": 120},
        {"label": "عدد ساعات الاوفر تايم", "fieldname": "Overtime Hours", "fieldtype": "Data", "width": 120},
        {"label": "عدد ساعات بدون الاوفر تايم", "fieldname": "Non-Ot Hours", "fieldtype": "Data", "width": 120},
        {"label": "عدد أيام الحضور", "fieldname": "Days Attended", "fieldtype": "Int", "width": 120},
        {"label": "عدد أيام الغياب", "fieldname": "Days Absent", "fieldtype": "Int", "width": 120},
        {"label": "اجمالي الاستحقاقات", "fieldname": "Earnings", "fieldtype": "Currency", "width": 120},
        {"label": "اجمالي الخصومات", "fieldname": "Deductions", "fieldtype": "Currency", "width": 120},
        {"label": "صافي الاستحقاقات", "fieldname": "Net Earnings", "fieldtype": "Currency", "width": 120},
    ]


def get_additional_salary(employee, week_start, week_end):
    try:
        query = """
        SELECT
            type,
            SUM(amount) AS total_amount
        FROM
            `tabAdditional Salary`
        WHERE
            employee = %s AND payroll_date BETWEEN %s AND %s
        GROUP BY
            type
        """
        additional_salaries = frappe.db.sql(query, (employee, week_start, week_end), as_dict=True)
        earnings = 0
        deductions = 0

        for salary in additional_salaries:
            if salary.get('type') == 'Earning':
                earnings += salary.get('total_amount', 0)
            elif salary.get('type') == 'Deduction':
                deductions += salary.get('total_amount', 0)

        return {'Earnings': earnings, 'Deductions': deductions}

    except Exception as e:
        frappe.throw(f"An error occurred while fetching additional salary: {str(e)}")
