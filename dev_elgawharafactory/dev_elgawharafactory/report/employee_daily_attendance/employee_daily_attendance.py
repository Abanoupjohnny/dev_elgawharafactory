import frappe
from datetime import datetime, timedelta

def execute(filters=None):
    try:
        columns = get_columns()
        filters = frappe._dict(filters)
        data = get_data(filters)
        return columns, data
    except ImportError as e:
        frappe.throw(f"Import Error: {str(e)}")
    except Exception as e:
        frappe.throw(f"An error occurred: {str(e)}")

def get_data(filters):
    try:
        conditions = get_conditions(filters)
        query = f"""
        SELECT
            emp.name AS `Employee ID`,
            emp.designation AS `Designation`,
            emp.branch AS `Branch`,
            DATE(chk.time) AS `Attendance Date`,
            chk.shift AS `Shift Type`,
            MIN(CASE WHEN chk.log_type = 'IN' THEN chk.time END) AS `Checkin Time`,
            MAX(CASE WHEN chk.log_type = 'OUT' THEN chk.time END) AS `Checkout Time`
        FROM
            `tabEmployee Checkin` chk
        JOIN
            `tabEmployee` emp ON chk.employee = emp.name
        LEFT JOIN
            `tabShift Type` shift ON shift.name = emp.default_shift
        LEFT JOIN
            `tabAdditional Salary` add_sal 
            ON emp.name = add_sal.employee 
            AND DATE(chk.time) BETWEEN add_sal.payroll_date AND add_sal.payroll_date
        {conditions}
        GROUP BY
            emp.name, DATE(chk.time)
        HAVING
            MIN(CASE WHEN chk.log_type = 'IN' THEN chk.time END) IS NOT NULL
            AND MAX(CASE WHEN chk.log_type = 'OUT' THEN chk.time END) IS NOT NULL
        ORDER BY
            emp.name, DATE(chk.time)
        """
        
        # Debugging print statements
        print(f"Query: {query}")
        print(f"Parameters: {filters}")

        data = frappe.db.sql(query, filters, as_dict=1)

        for row in data:
            shift_type = row['Shift Type']
            shift_details = frappe.get_doc("Shift Type", shift_type)

            checkin_time = row['Checkin Time']
            checkout_time = row['Checkout Time']
            
            shift_start_time = datetime.combine(row['Attendance Date'], convert_timedelta_to_time(shift_details.start_time))
            shift_end_time = datetime.combine(row['Attendance Date'], convert_timedelta_to_time(shift_details.end_time))

            # Adjust checkin and checkout times based on shift start and end times
            if checkin_time < shift_start_time:
                checkin_time = shift_start_time

            # if checkout_time > shift_end_time:
            #     checkout_time = shift_end_time

            if checkin_time and checkout_time:
                total_hours = checkout_time - checkin_time
                
                # Calculate overtime and non-overtime hours
                if checkout_time > shift_end_time:
                    overtime_hours = checkout_time - shift_end_time
                else:
                    overtime_hours = timedelta(0)
                    
                non_overtime_hours = total_hours - overtime_hours

                row['Total Hours'] = format_timedelta(total_hours)
                row['Overtime Hours'] = format_timedelta(overtime_hours)
                row['Non-Overtime Hours'] = format_timedelta(non_overtime_hours)

            additional_salary = get_additional_salary(row['Employee ID'], row['Attendance Date'])
            row['Deductions'] = additional_salary.get('Deductions', 0)
            row['Earnings'] = additional_salary.get('Earnings', 0)
            row['Net Earnings'] = row['Earnings'] - row['Deductions']

        return data
    except Exception as e:
        frappe.throw(f"An error occurred while fetching data: {str(e)}")

def convert_timedelta_to_time(td):
    return (datetime.min + td).time()

def format_timedelta(td):
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h {minutes}m {seconds}s"

def get_conditions(filters):
    conditions = []

    if filters.get('from_date') and filters.get('to_date'):
        conditions.append("DATE(chk.time) BETWEEN %(from_date)s AND %(to_date)s")
    if filters.get('employee'):
        conditions.append("chk.employee = %(employee)s")
    if filters.get('designation'):
        conditions.append("emp.designation = %(designation)s")
    if filters.get('branch'):
        conditions.append("emp.branch = %(branch)s")

    if conditions:
        return "WHERE " + " AND ".join(conditions)
    else:
        return ""

def get_columns():
    return [
        {"label": "اسم الموظف", "fieldname": "Employee ID", "fieldtype": "Link", "options": "Employee", "width": 150},
        {"label": "المسمى الوظيفي", "fieldname": "Designation", "fieldtype": "Link", "options": "Designation", "width": 120},
        {"label": "الفرع", "fieldname": "Branch", "fieldtype": "Link", "options": "Branch", "width": 120},
        {"label": "تاريخ الحضور", "fieldname": "Attendance Date", "fieldtype": "Date", "width": 120},
        {"label": "نوع الشيفت", "fieldname": "Shift Type", "fieldtype": "Link", "options": "Shift Type", "width": 100},
        {"label": "وقت الحضور", "fieldname": "Checkin Time", "fieldtype": "Data", "width": 100},
        {"label": "وقت الانصراف", "fieldname": "Checkout Time", "fieldtype": "Data", "width": 100},
        {"label": "اجمالي عدد الساعات", "fieldname": "Total Hours", "fieldtype": "Data", "width": 120},
        {"label": "عدد ساعات الاوفر تايم", "fieldname": "Overtime Hours", "fieldtype": "Data", "width": 120},
        {"label": "عدد ساعات بدون الاوفر تايم", "fieldname": "Non-Overtime Hours", "fieldtype": "Data", "width": 120},
        {"label": "اجمالي الاستحقاقات", "fieldname": "Earnings", "fieldtype": "Currency", "width": 120},
        {"label": "اجمالي الخصومات", "fieldname": "Deductions", "fieldtype": "Currency", "width": 120},
        {"label": "صافي الاستحقاقات", "fieldname": "Net Earnings", "fieldtype": "Currency", "width": 120},
    ]

def get_additional_salary(employee, date):
    try:
        query = """
        SELECT
            type,
            SUM(amount) AS total_amount
        FROM
            `tabAdditional Salary`
        WHERE
            employee = %s AND %s BETWEEN payroll_date AND payroll_date
        GROUP BY
            type
        """
        additional_salaries = frappe.db.sql(query, (employee, date), as_dict=True)

        earnings = 0
        deductions = 0

        for salary in additional_salaries:
            if salary.get('type') == 'Earning':
                earnings += salary.get('total_amount', 0)
            elif salary.get('type') == 'Deduction':
                deductions += salary.get('total_amount', 0)

        return {'Earnings': earnings, 'Deductions': deductions}
    except Exception as e:
        frappe.throw(f"Error fetching additional salary for {employee} on {date}: {str(e)}")
