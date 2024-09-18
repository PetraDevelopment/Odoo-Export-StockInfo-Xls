{
    'name': 'Export Product Stock in Excel',
    
    'depends': ['sale_management','stock','purchase'],
    'author':'Petra Software',
    'company': 'Petra Software',
    'maintainer': 'Petra Software',
    'website':'www.t-petra.com',
    'data': [
        'security/ir.model.access.csv',
        'wizard/stock_report_views.xml',
        'reports/pdf_report_template.xml',
        'reports/pdf_report.xml',
        
    ],
    'assets': {
        'web.assets_backend': [
            'export_stockinfo_excel/static/src/js/action_manager.js',
        ],
    },
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'auto_install': False,
    'images': ['static/description/banner.png'],
      'price':22,
    'currency':'USD',
}
