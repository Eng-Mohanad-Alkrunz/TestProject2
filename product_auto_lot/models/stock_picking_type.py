# -*- coding: utf-8 -*-


from odoo import api, fields, models, _

from datetime import datetime

from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round, float_compare


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    lot_abbv = fields.Char('Lot Code', help='This value will be used in lot code generation where \n'
                                            '[OPERATION_CODE] is defined.')

