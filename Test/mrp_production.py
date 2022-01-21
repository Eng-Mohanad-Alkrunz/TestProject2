# -*- coding: utf-8 -*-

import math
from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    def action_generate_serial(self):
        self.ensure_one()
        self.lot_producing_id = 120
        if self.move_finished_ids.filtered(lambda m: m.product_id == self.product_id).move_line_ids:
            self.move_finished_ids.filtered(lambda m: m.product_id == self.product_id).move_line_ids.lot_id = self.lot_producing_id
        if self.product_id.tracking == 'serial':
            self._set_qty_producing()

            # self.env['stock.lot'].create({
            #     'product_id': self.product_id.id,
            #     'company_id': self.company_id.id,
            #     'name': self.env['stock.lot']._get_next_serial(self.company_id, self.product_id) or self.env[
            #         'ir.sequence'].next_by_code('stock.lot.serial'),
            # })
