# -*- coding: utf-8 -*-

from odoo import api, exceptions, fields, models, _
from odoo.addons import decimal_precision as dp


class StockProductionLot(models.Model):
    _inherit = 'stock.production.lot'

    quantity_location = fields.Float('Qty', compute='_compute_quantity_location')

    @api.depends('quant_ids.quantity')
    def _compute_quantity_location(self):
        for rec in self:
            # If there is a workorder in the context, get quantities from the current production location.
            if rec.env.context.get('mrp_workorder'):
                # Get the location and child locations of the current production order.
                mrp_workorder = self.env['mrp.workorder'].browse(rec.env.context.get('mrp_workorder'))
                child_locations = self.env['stock.location'].search(
                    [('location_id', 'child_of', mrp_workorder.production_id.location_src_id.id)])
    
            else:
                # Get all internal locations.
                child_locations = self.env['stock.location'].search([('location_id.usage', '=', 'internal')])
    
            self.quantity_location = sum(self.quant_ids.filtered(lambda x: bool(set(x.mapped('location_id').ids) & set(child_locations.ids))).mapped('quantity'))

    def name_get(self):
        if self.env.context.get('show_product_name') and self.env.context.get('mrp_workorder'):
            mrp_workorder = self.env['mrp.workorder'].browse(self.env.context.get('mrp_workorder'))
            child_locations = self.env['stock.location'].search(
                [('location_id', 'child_of', mrp_workorder.production_id.location_src_id.id)])
            res = []
            for lot in self:
                # get the name of the product, and quantity. sum the total quantity only if all quants use same uom.
                quantity_at_location = sum(lot.mapped('quant_ids').filtered(lambda x: bool(set(x.mapped('location_id').ids) & set(child_locations.ids))).mapped('quantity'))

                res.append((lot.id, lot.name + ' ' + '[' + lot.product_id.name + ']' + ' | QTY: ' + '{0:,.3f}'.format(quantity_at_location) + ' ' + lot.product_id.uom_id.name))
        else:
            res = super(StockProductionLot, self).name_get()
        return res

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self.env.context.get('show_product_name'):
            mrp_workorder = self.env['mrp.workorder'].browse(self.env.context.get('mrp_workorder'))
            lot = self.env['stock.production.lot']
            # TODO: Redo by searching for stock.quant and using mapped()?
            if not args:
                args = [('id', 'not in', [])]
            if name:
                lot = self.search(['&', ('name', operator, name), ('product_id', 'in', mrp_workorder.raw_product_ids.ids)], limit=1000)
            else:
                lot = self.search(args + [('product_id', 'in', mrp_workorder.production_id.mapped('move_raw_ids.product_id').ids)], limit=1000)

            # Filter for lots that have quants at the manufacturing location and its children locations.
            child_locations = self.env['stock.location'].search([('location_id', 'child_of', mrp_workorder.production_id.location_src_id.id)])

            # lot = lot.filtered(lambda x: any(a in x.mapped('quant_ids.location_id').ids for a in child_locations.ids))
            lot = lot.filtered(lambda x: bool(set(x.mapped('quant_ids.location_id').ids) & set(child_locations.ids)))

            # Filter for lots who have a postive sum among its quants at this location.
            # Then take the real_limit
            # lot = lot.filtered(lambda x: sum(x.mapped('quant_ids').filtered(lambda y: any(x in y.mapped('location_id').ids for x in child_locations.ids)).mapped('qty')) > 0)[:real_limit]
            lot = lot.filtered(lambda x: sum(x.mapped('quant_ids').filtered(lambda y: any(x in y.mapped('location_id').ids for x in child_locations.ids)).mapped('quantity')) > 0)

            return lot.name_get()
        else:
            return super(StockProductionLot, self).name_search(name, args=args, operator=operator, limit=limit)

