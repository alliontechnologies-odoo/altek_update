{
	'name': 'Altek Sales Reports',
	'version': '1.0',
	'sequence': 1,
	'author': "Centrics Business Solutions PVT Ltd",
	'website': 'http://www.centrics.cloud/',
	'summary': 'This module contains all the custom reports that related to Sales Module',
	'description': """This module contains all the custom reports that related to Sales Module""",
	'category': 'Tools',
	'depends': ['base', 'sale', 'altek_indent_process'],
	'external_dependencies': {},
	'data': [
		'security/ir.model.access.csv',
		'wizards/sales_gp_report_view.xml',
	],
	'demo': [],
	'installable': True,
	'application': True,
	'auto_install': False,
}