// Copyright (c) 2024, Abanoub Johnny and contributors
// For license information, please see license.txt

frappe.query_reports["Employee Summary Attandance"] = {
	"filters": [
		{
			label: 'Employee',
			fieldname: 'employee',
			fieldtype: 'Link',
			options: 'Employee'
		},
		{
			label: 'Designation',
			fieldname: 'designation',
			fieldtype: 'Link',
			options: 'Designation'
		},
		{
			label: 'Branch',
			fieldname: 'branch',
			fieldtype: 'Link',
			options: 'Branch'
		},
		{
			label: 'Start Date',
			fieldname: 'start_date',
			fieldtype: 'Date',
			reqd:0
		},
		{
			label: 'End Date',
			fieldname: 'start_date',
			fieldtype: 'Date',
			reqd:0
		},
	]
};
