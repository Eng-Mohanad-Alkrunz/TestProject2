# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = 'stock.move'

    stock_pickup_date = fields.Datetime('Pickup Date', compute='_get_pickup_date', store=True)

    @api.depends('picking_id')
    def _get_pickup_date(self, recompute=False):
        if recompute and not self:
            self = self.search([('picking_id', '!=', False), ('picking_id.sale_id', '!=', False), ('state', 'not in', ['done', 'cancel'])])

        for move in self:
            if move.picking_id and move.picking_id.sale_id:
                if move.picking_id.stock_pickup_date:
                    move.stock_pickup_date = move.picking_id.stock_pickup_date
                elif move.picking_id.sale_id.expected_date:
                    move.stock_pickup_date = move.picking_id.sale_id.expected_date
                else:
                    move.stock_pickup_date = move.picking_id.sale_id.confirmation_date

