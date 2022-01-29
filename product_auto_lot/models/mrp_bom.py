# -*- coding: utf-8 -*-


from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.addons import decimal_precision as dp


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    product_qty_per_pallet = fields.Float('Product Quantity per Pallet', default=1,
                                          digits=dp.get_precision('Product Unit of Measure'), required=True)

