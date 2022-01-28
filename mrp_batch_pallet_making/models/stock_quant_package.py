# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools import float_compare, float_round, float_is_zero


class StockQuantPackageStartTime(models.Model):
    _inherit = 'stock.quant.package'

    start_date = fields.Datetime('Start Date')
    end_date = fields.Datetime('End Date')
