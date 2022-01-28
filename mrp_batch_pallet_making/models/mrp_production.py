# -*- coding: utf-8 -*-

import math
from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    select_lot_ids = fields.Many2many('stock.production.lot', string='Select Lot Codes', store=False, create_edit=False,
                                      help='Select a lot code to add to this workorder.')

    raw_product_ids = fields.Many2many('product.product', compute='_raw_product_ids')

    product_qty_per_workcenter = fields.Float(
        'Quantity',
        required=True, states={'done': [('readonly', True)]},
        compute='_get_qty_per_workcenter')


    @api.returns('stock.production.lot')
    def _get_top_three_lot_ids(self, product_id):
        self.ensure_one()
        stock_production_lot = self.env['stock.production.lot']

        # Get all the child locations of the source location.
        child_locations = self.env['stock.location'].search(
            [('location_id', 'child_of', self.production_id.location_src_id.id)])

        # Get the lots that have quants at our child locations.
        lot_ids = stock_production_lot.search(
            [('product_id', '=', product_id), ('quant_ids.location_id', 'in', child_locations.ids)])

        # Filter out lots with negative or zero quantity.
        # Sort the lots by the qty available at the locations.
        # TODO: This should be done in a FEFO/FIFO way based on product category.
        sorted_lot_ids = lot_ids.filtered(lambda x: sum(x.mapped('quant_ids').filtered(
            lambda s: bool(set(s.mapped('location_id').ids) & set(child_locations.ids))).mapped('quantity')) >= 0) \
            .sorted(lambda x: sum(x.mapped('quant_ids').filtered(
            lambda s: bool(set(s.mapped('location_id').ids) & set(child_locations.ids))).mapped('quantity')),
                    reverse=True)

        # Return only the top 3.
        return sorted_lot_ids[:3]


    def _raw_product_ids(self):
        for rec in self:
            #             for raw in rec.production_id.move_raw_ids:
            #                 print(raw.workorder_id)
            product_ids = rec.production_id.move_raw_ids.filtered(lambda x: x.workorder_id.id == rec.id).mapped(
                'product_id')
            #             product_ids = rec.move_line_ids.mapped('product_id')
            rec.raw_product_ids = [(4, x.id) for x in product_ids]

    @api.onchange('select_lot_ids')
    def _select_lot(self):
        if self.select_lot_ids:
            lot_ids = self.select_lot_ids.filtered(
                lambda x: x._origin not in self.production_id.move_raw_ids.mapped('move_line_ids').mapped('lot_id'))
            #             lot_ids = self.select_lot_ids.filtered(lambda x: x not in self.move_line_ids.mapped('lot_id'))

            for lot in lot_ids:
                active_moves = self.production_id.move_raw_ids.mapped('move_line_ids').filtered(
                    lambda x: x.product_id.id == lot.product_id.id)
                #                 active_moves = self.move_line_ids.filtered(lambda x: x.product_id.id == lot.product_id.id)
                if not active_moves:
                    move_raw = self.production_id.move_raw_ids.filtered(lambda x: x.product_id.id == lot.product_id.id)
                if active_moves:
                    blank_move_lot = active_moves.filtered(lambda m: not m.lot_id)
                    move_lots = active_moves.filtered(lambda m: m.lot_id.id == lot._origin.id)
                    child_location = self.env['stock.location'].search(
                        [('location_id', 'child_of', self.production_id.location_src_id.id)])
                    quantity_at_location = sum(lot.mapped('quant_ids').filtered(
                        lambda x: bool(set(x.mapped('location_id').ids) & set(child_location.ids))).mapped('quantity'))
                    # Get the remaining quantity to do.
                    quantity_done = active_moves.filtered(lambda m: m.lot_id.id).mapped('qty_done')
                    quantity = active_moves.mapped('product_uom_qty')
                    quantity_todo = sum(quantity) - sum(quantity_done)
                    if move_lots:

                        return
                    elif blank_move_lot:
                        blank_move_lot[0].lot_id = lot._origin.id
                        blank_move_lot._origin[0].qty_done = max(min(quantity_at_location, quantity_todo), 0)
                    else:
                        location_dest_id = active_moves[0].move_id.location_dest_id._get_putaway_strategy(
                            lot.product_id).id or active_moves[0].move_id.location_dest_id.id
                        self.move_line_ids.create({'move_id': active_moves[0].move_id.id,
                                                   'lot_id': lot._origin.id,
                                                   #                                                       'quantity_done': max(min(quantity_at_location, quantity_todo), 0),
                                                   'qty_done': max(min(quantity_at_location, quantity_todo), 0),
                                                   'product_uom_qty': 0.0,
                                                   'workorder_id': self._origin.id,
                                                   'production_id': self.production_id.id,
                                                   'location_id': active_moves[0].move_id.location_id.id,
                                                   'location_dest_id': location_dest_id,
                                                   'product_uom_id': lot.product_id.uom_id.id,
                                                   'product_id': lot.product_id.id})
                #                                                       'done_wo': False})
                elif move_raw:
                    # If the move lot is missing or was deleted, we can create a new one.
                    child_location = self.env['stock.location'].search(
                        [('location_id', 'child_of', self.production_id.location_src_id.id)])

                    quantity_at_location = sum(lot.mapped('quant_ids').filtered(
                        lambda x: bool(set(x.mapped('location_id').ids) & set(child_location.ids))).mapped('quantity'))
                    quantity_todo = move_raw.unit_factor * self.qty_producing
                    #                     location_ids = lot.mapped('quant_ids').mapped('location_id')
                    location_dest_id = move_raw.location_dest_id._get_putaway_strategy(
                        lot.product_id).id or move_raw.location_dest_id.id
                    self.production_id.move_raw_ids.move_line_ids.create({'move_id': move_raw.id,
                                                                          'lot_id': lot._origin.id,
                                                                          'qty_done': max(
                                                                              min(quantity_at_location, quantity_todo),
                                                                              0),
                                                                          'product_uom_id': lot.product_id.uom_id.id,
                                                                          'product_uom_qty': quantity_todo,
                                                                          'workorder_id': self._origin.id,
                                                                          'production_id': self.production_id.id,
                                                                          #                                                   'location_id':location_ids and location_ids[0].id,
                                                                          'location_id': move_raw.location_id.id,
                                                                          'location_dest_id': location_dest_id,
                                                                          'product_id': lot.product_id.id})



    def action_generate_serial(self):
        self.ensure_one()

        self.lot_producing_id = self.env['stock.production.lot'].create({
            'product_id': self.product_id.id,
            'company_id': self.company_id.id,
            'name': self.product_id.gen_lot_code(),
        })
        if self.move_finished_ids.filtered(lambda m: m.product_id == self.product_id).move_line_ids:
            self.move_finished_ids.filtered(
                lambda m: m.product_id == self.product_id).move_line_ids.lot_id = self.lot_producing_id
        if self.product_id.tracking == 'serial':
            self._set_qty_producing()

    def action_view_import_packages_wizard(self):
        self.ensure_one()

        action = self.env.ref('mrp_batch_pallet_making.action_view_import_package_wizard')
        form_view_id = self.env.ref('mrp_batch_pallet_making.view_import_package_wizard').id
        context = dict(self.env.context or {})
        context['default_production_id'] = self.id

#         action.context = str({
#             'default_production_id': self.id,
#         })


        result = {
                'name': _(action.name),
                'view_mode': 'form',
                'res_model': action.model_id.model,
                'view_id': form_view_id,
                'type': 'ir.actions.act_window',
#                 'res_id': self.id,
                'context': context,
                'target': 'new'
            }
        return result

    def action_import_packages(self):
        self.ensure_one()

        if self.product_id.lot_abbv and '[USER_DEFINED' in self.product_id.lot_abbv:
            return self.action_view_import_packages_wizard()

        gen_date = self.date_planned_start
#         gen_date = datetime.strptime(self.date_planned_start, DEFAULT_SERVER_DATETIME_FORMAT)
        lot_code = self.product_id.with_context(default_production_id=self.id).gen_lot_code(gen_date=gen_date)
        lot_id = self.env['stock.production.lot'].search([('name', '=', lot_code), ('product_id', '=', self.product_id.id)])

        if lot_id:
            packages = self.env['stock.quant.package'].search([('default_lot_code_id', '=', lot_id.id), ('end_date', '=', False)])
            if not packages:
                raise UserError("No packages were found.")

            if packages:
                packages.write({'production_id': self.id})
                current_step = packages.sorted(key=lambda r: r.pallet_number)[0].pallet_number - 1
                self.workorder_ids.write({'finished_lot_id': packages[0].default_lot_code_id.id})
                if current_step > 0:
                    self.workorder_ids.write({'current_step': current_step})


    def _get_qty_per_workcenter(self):
        for mo in self:
            routing_id = self.env['mrp.routing.workcenter'].search([('workcenter_id','in',mo.workorder_ids.ids)], limit=1)
            if routing_id and routing_id.routing_type == 'parallel':
                wo_count = len(mo.workorder_ids)
                if wo_count:
                    mo.product_qty_per_workcenter = mo.product_qty / wo_count
                else:
                    mo.product_qty_per_workcenter = mo.product_qty
            else:
                mo.product_qty_per_workcenter = mo.product_qty



