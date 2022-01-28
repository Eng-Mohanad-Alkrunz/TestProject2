# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import float_compare, float_round, float_is_zero


class StockMoveLots(models.Model):
    _inherit = 'stock.move.lots'

    active_lot = fields.Boolean('Active', default=True)

