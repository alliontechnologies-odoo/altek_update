{
    'name': "Local Bank Config",
    'version': '1.0',
    'summary': """Local Bank Config""",
    'sequence': 1,
    'description': """Local Bank Config""",
    'author': "Centrics Business Solutions (Pvt) Ltd",
    'website': 'http://www.centrics.cloud/',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/main_bank_view.xml',
        'views/inherit_res_bank_view.xml',
        'views/inherit_res_partner_bank_view.xml',
        # 'views/inherit_res_partner.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': True,
}