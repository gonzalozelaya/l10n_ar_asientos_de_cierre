# -*- coding: utf-8 -*-
{
    'name': "Generador Asientos de cierre",

    'summary': """
        Permite generar asientos de cierre para el modulo de contabilidad""",

    'description': """
        Permite generar asientos de cierre para el modulo de contabilidad
    """,

    'author': "OutsourceArg",
    'website': "http://www.outsourcearg.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '1.0',

    # any module necessary for this one to work correctly
    'depends': ['account'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/asiento_final.xml',
        'views/wizard_views.xml',
        'reports/report_final.xml',
    ],

}