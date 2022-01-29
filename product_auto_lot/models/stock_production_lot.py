# -*- coding: utf-8 -*-

import datetime
from odoo import api, fields, models
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT


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

            self.quantity_location = sum(self.quant_ids.filtered(
                lambda x: bool(set(x.mapped('location_id').ids) & set(child_locations.ids))).mapped('quantity'))

    def name_get(self):
        if self.env.context.get('show_product_name') and self.env.context.get('mrp_workorder'):
            mrp_workorder = self.env['mrp.workorder'].browse(self.env.context.get('mrp_workorder'))
            child_locations = self.env['stock.location'].search(
                [('location_id', 'child_of', mrp_workorder.production_id.location_src_id.id)])
            res = []
            for lot in self:
                # get the name of the product, and quantity. sum the total quantity only if all quants use same uom.
                quantity_at_location = sum(lot.mapped('quant_ids').filtered(
                    lambda x: bool(set(x.mapped('location_id').ids) & set(child_locations.ids))).mapped('quantity'))

                res.append((lot.id, lot.name + ' ' + '[' + lot.product_id.name + ']' + ' | QTY: ' + '{0:,.3f}'.format(
                    quantity_at_location) + ' ' + lot.product_id.uom_id.name))
        else:
            res = super(StockProductionLot, self).name_get()
        return res

    # @api.model
    # def name_search(self, name='', args=None, operator='ilike', limit=100):
    #     if self.env.context.get('show_product_name'):
    #         mrp_workorder = self.env['mrp.workorder'].browse(self.env.context.get('mrp_workorder'))
    #         lot = self.env['stock.production.lot']
    #         # TODO: Redo by searching for stock.quant and using mapped()?
    #         if not args:
    #             args = [('id', 'not in', [])]
    #         if name:
    #             lot = self.search(
    #                 ['&', ('name', operator, name), ('product_id', 'in', mrp_workorder.raw_product_ids.ids)],
    #                 limit=1000)
    #         else:
    #             lot = self.search(
    #                 args + [('product_id', 'in', mrp_workorder.production_id.mapped('move_raw_ids.product_id').ids)],
    #                 limit=1000)
    #
    #         # Filter for lots that have quants at the manufacturing location and its children locations.
    #         child_locations = self.env['stock.location'].search(
    #             [('location_id', 'child_of', mrp_workorder.production_id.location_src_id.id)])
    #
    #         # lot = lot.filtered(lambda x: any(a in x.mapped('quant_ids.location_id').ids for a in child_locations.ids))
    #         lot = lot.filtered(lambda x: bool(set(x.mapped('quant_ids.location_id').ids) & set(child_locations.ids)))
    #
    #         # Filter for lots who have a postive sum among its quants at this location.
    #         # Then take the real_limit
    #         # lot = lot.filtered(lambda x: sum(x.mapped('quant_ids').filtered(lambda y: any(x in y.mapped('location_id').ids for x in child_locations.ids)).mapped('qty')) > 0)[:real_limit]
    #         lot = lot.filtered(lambda x: sum(x.mapped('quant_ids').filtered(
    #             lambda y: any(x in y.mapped('location_id').ids for x in child_locations.ids)).mapped('quantity')) > 0)
    #
    #         return lot.name_get()
    #     else:
    #         return super(StockProductionLot, self).name_search(name, args=args, operator=operator, limit=limit)

    gen_date = fields.Datetime('Manufactured Date')

    quantity_context = fields.Float('Quantity to Pack', compute='_product_qty_at_context', help='Quantity at location based on context.')
    quantity_tentatively_packed = fields.Float('Quantity Packed', compute='_product_qty_at_context', help='Quantity that has been packed in picking.')
    quantity_to_pack = fields.Float('Quantity Remaining', compute='_product_qty_at_context', help='Quantity left to pack.')

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if self.env.context.get('select_from_packages'):
            mrp_workorder = self.env['mrp.workorder'].browse(self.env.context.get('mrp_workorder'))

            default_lots = mrp_workorder.production_id.package_ids.mapped('default_lot_code_id')

            if not args:
                args = []
            if name:
                lot = self.search(
                    ['&', ('name', operator, name), ('id', 'in', default_lots.ids)] + args,
                    limit=1000)
            else:
                lot = self.search(['&', ('id', 'in', default_lots.ids)] + args, limit=1000)

            return lot.name_get()
        else:
            return super(StockProductionLot, self).name_search(name, args=args, operator=operator, limit=limit)

#     @api.one
    def _use_gen_date(self):
        dates_dict = self._get_dates()

        for field, value in dates_dict.items():
            setattr(self, field, value)

#     @api.one
    def _product_qty_at_context(self):

        if self.env.context.get('default_production_id', False):
            production_id = self.env['mrp.production'].browse(self.env.context.get('default_production_id'))

            location_id = production_id.location_dest_id.id
            # Get all the quant_ids from the production order.
#             quant_ids = production_id.mapped('move_finished_ids.quant_ids')
            quant_ids =  production_id.move_finished_ids.move_line_ids.mapped('lot_id').mapped('quant_ids')
            self.quantity_context = sum(self.quant_ids.filtered(lambda x: x.location_id.id == location_id and x.id in quant_ids.ids).mapped('quantity'))

            manu_pack_type_id = production_id.picking_type_id.warehouse_id.manu_packing_type_id
            pack_lot_ids = production_id.picking_ids.filtered(lambda pick: pick.picking_type_id.id == manu_pack_type_id.id
                                                                 and pick.state not in ['done', 'cancel']).mapped(
                                                                 'move_line_ids_without_package').filtered(
                                                                 lambda op: op.product_id.id == self.product_id.id
                                                                 and op.result_package_id.id
                                                                 and self.id in op.pack_lot_ids.mapped('lot_id').ids)
            self.quantity_tentatively_packed = sum(pack_lot_ids.mapped('qty_done'))

            self.quantity_to_pack = self.quantity_context - self.quantity_tentatively_packed

        elif self.env.context.get('default_location_id'):
            location_id = self.env.context.get('default_location_id')
            self.quantity_context = sum(self.quant_ids.filtered(lambda x: x.location_id.id == location_id).mapped('quantity'))

