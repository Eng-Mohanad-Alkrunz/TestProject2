# -*- coding: utf-8 -*-
# © 2018 Mark Robinson, J3 Solution
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    'name': 'Product - Lot Code Usability Enhancements',
    'version': '14.0.1.0.0',
    'license': 'LGPL-3',
    'category': 'Inventory',
    'depends': ['product', 'stock', 'mrp', 'product_expiry'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_picking.xml',
        'views/product.xml',
#         'views/stock_pack_operation_views.xml',
        'views/stock_warehouse.xml',
        'views/mrp_workcenter.xml',
        'views/mrp_bom.xml',
        'views/stock_production_lot.xml',

#         'report/stock_picking_lot_report.xml',
#         'report/stock_picking_lot_standard_report.xml',
        'report/mrp_production_lot_report.xml',
        'report/report_paperformat_data.xml',
        'report/report_stock_package.xml',
        'report/lot_code_report.xml',
        'views/mrp_workorder.xml',
        'views/mrp_production.xml',
        'views/stock_picking_type.xml',
        'views/stock_quant_package.xml',
        # 'views/workorder_batch_ui.xml',
        # 'views/workorder_pallet_ui.xml',
#         'report/mrp_workorder_lot_report.xml',
        'wizard/mrp_generate_lot.xml',
        'wizard/mrp_generate_pallet.xml',
        'wizard/mrp_pack_pallet.xml',
        'wizard/mrp_unpack_pallet.xml',


    ],
    'installable': True,
    'application': True,
}
