# -*- coding: utf-8 -*-


from odoo import api, fields, models, _

from datetime import datetime

from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round, float_compare

import string

# class PackOperation(models.Model):
#     _name = "stock.pack.operation"
#
#     location_id = fields.Many2one('stock.location', 'Source Location', required=True)
#     location_dest_id = fields.Many2one('stock.location', 'Destination Location', required=True)


class PackOperationLot(models.Model):
    _inherit = "stock.move"



    # lot_name = fields.Char('Lot/Serial Number', compute='_get_lot_number', inverse='_set_lot_number')

    # def _parse_lot_code(self, lot_abbv):
    #     lot_name = lot_abbv
    #     lot_name = string.replace(lot_name, '[JULIAN]', '%d%03d' % (datetime.now().timetuple().tm_year, datetime.now().timetuple().tm_yday), 1)
    #     lot_name = string.replace(lot_name, '[DATE]', fields.Date.to_string(datetime.now()), 1)
    #     #TODO: implement STATION_CODE and WAREHOUSE_CODE
    #     lot_name = string.replace(lot_name, '[STATION_CODE]', '', 1)
    #     lot_name = string.replace(lot_name, '[WAREHOUSE_CODE]', '', 1)
    #     #TODO: Replace any sequential dashes with single dashes.
    #     return lot_name
    #
    # @api.onchange('operation_id', 'qty', 'qty_todo')
    # def _get_lot_number(self):
    #     for lot in self:
    #         if lot.operation_id.product_id.lot_abbv and lot.lot_name is False:
    #             lot_name = lot._parse_lot_code(lot.operation_id.product_id.lot_abbv)
    #             lot.lot_name = lot_name
    #
    # def _set_lot_number(self):
    #     return

