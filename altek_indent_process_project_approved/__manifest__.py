{
    'name': 'Altek Indent Process for Approved Projects',
    'version': '1.0',
    'sequence': 1,
    'author': "Centrics Business Solutions PVT Ltd",
    'website': 'http://www.centrics.cloud/',
    'summary': """This module contains entire Indent process of Altek International that related to 
    Approved Projects""",
    'description': """This module contains entire Indent process of Altek International that related to
    Approved Projects""",
    'depends': [
        'base', 'mail', 'sale_management', 'sale', 'purchase', 'local_banks_config', 'account', 'product', 'uom'
    ],
    'external_dependencies': {},
    'data': [
        'security/ir.model.access.csv',
        'security/security_groups.xml',
        'data/ir_sequence_data.xml',
        'data/mail_template.xml',
        'views/activity_view_inherit.xml',
        'views/indent_sector_view.xml',
        'views/account_incoterms_view.xml',
        'views/done_activity_view.xml',
        'views/account_move_views.xml',
        'views/indent_view.xml',
        'views/indent_sheet_view.xml',
        'views/res_company.xml',
        'views/res_partner_bank_view.xml',
        'views/res_partner.xml',
        'views/product_views.xml',
        'views/sale_order_views.xml',
        'views/indent_invoice_view.xml',
        'data/mail_activity_data.xml',
        'wizard/assign_user_view.xml',
        'wizard/comment_view.xml',
        'wizard/indent_make_invoice_advance_views.xml',
        'wizard/indent_report_view_wizard_view.xml',
        'views/indent_report_preview_view.xml',
        'data/product_data.xml',
        'reports/indent_sheet_report.xml',
        'reports/indent_report_preview_report.xml'
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}

