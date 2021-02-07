{
	'name': 'Altek Inventory Reports',
	'version': '1.0',
	'sequence': 1,
	'author': "Centrics Business Solutions PVT Ltd",
	'website': 'http://www.centrics.cloud/',
	'summary': 'This module contains all the custom reports that related to Inventory Module',
	'description': """This module contains all the custom reports that related to Inventory Module""",
	'category': 'Tools',
	'depends': ['base', 'stock', 'altek_indent_process'],
	'external_dependencies': {},
	'data': [
		'security/ir.model.access.csv',
		'wizards/slow_moving_report_view.xml',
		'wizards/expire_stock_report_view.xml',
	],
	'demo': [],
	'installable': True,
	'application': True,
	'auto_install': False,
}