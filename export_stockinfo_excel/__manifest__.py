
{
    'name': 'Export Product Stock in Excel',
   
    'depends': ['base','stock','sale','purchase',],
     'author':'Petra Software',
    'company': 'Petra Software',
    'maintainer': 'Petra Software',
    'website':'www.t-petra.com',
    'data': [
        'views/wizard_view.xml',
        'views/action_manager.xml',
        'security/ir.model.access.csv',
        'reports/pdf_report_template.xml',
        'reports/pdf_report.xml',
    ],
      'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'auto_install': False,
      'price':22,
    'currency':'USD',
}
