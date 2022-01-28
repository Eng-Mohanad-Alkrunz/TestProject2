# -*- coding: utf-8 -*-

from odoo import api, exceptions, fields, models, _
from odoo.addons import decimal_precision as dp


class StockQuant(models.Model):
    _inherit = 'stock.quant'

