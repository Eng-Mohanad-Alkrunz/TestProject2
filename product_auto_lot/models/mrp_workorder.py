# -*- coding: utf-8 -*-


from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.addons import decimal_precision as dp


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    select_lot_ids = fields.Many2many('stock.production.lot', string='Select Lot Codes', store=False, create_edit=False,
                                      help='Select a lot code to add to this workorder.')

    raw_product_ids = fields.Many2many('product.product', compute='_raw_product_ids')

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

    gen_date = fields.Datetime('Date of Manufacture') # Legacy, no longer used. Use date_planned_start instead.


    def generate_final_lot_code(self):
        for wo in self:
            if wo.product_id.lot_abbv and '[USER_DEFINED' in wo.product_id.lot_abbv:
                return wo.action_view_generate_lot_wizard()
            else:
#                 gen_date = datetime.strptime(self.date_planned_start or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
                gen_date = self.date_planned_start or fields.Datetime.now()
                lot_name = wo.product_id.gen_lot_code(gen_date=gen_date)
                existing_lots = self.env['stock.production.lot'].search([('name', '=', lot_name), ('product_id', '=', wo.product_id.id)])

                if len(existing_lots.ids) > 0:
#                     wo.final_lot_id = existing_lots.ids[0]
                    wo.finished_lot_id = existing_lots.ids[0]
                else:
#                     wo.final_lot_id = wo.env['stock.production.lot'].create({
                    wo.finished_lot_id = wo.env['stock.production.lot'].create({
                        'name': lot_name,
                        'product_id': wo.product_id.id,
                        'gen_date': gen_date,
                    }).id
                    wo.finished_lot_id.sudo()._use_gen_date()
#                     wo.final_lot_id.sudo()._use_gen_date()
        return True

    def action_view_generate_lot_wizard(self):
        for wo in self:
#             imd = self.env['ir.model.data'].sudo()
#             action = imd.xmlid_to_object('product_auto_lot.action_view_generate_lot_code_wizard')
#             form_view_id = imd.xmlid_to_res_id('product_auto_lot.view_generate_lot_code_wizard')
# 
#             action.context = str({
#                 'default_workorder_id': wo.id,
#             })
# 
#             result = {
#                 'name': action.name,
#                 'help': action.help,
#                 'mode': action.type,
#                 'views': [[form_view_id, 'form']],
#                 'target': action.target,
#                 'context': action.context,
#                 'res_model': action.res_model,
#             }

            action = self.env.ref('product_auto_lot.action_view_generate_lot_code_wizard')
            form_view_id = self.env.ref('product_auto_lot.view_generate_lot_code_wizard').id
            context = dict(self.env.context or {})
            context['default_workorder_id'] = wo.id
    #         context['active_ids'] = [self.ids]
    #         context['active_model'] = 'mrp.production'
            result = {
                    'name': _(action.name),
                    'view_mode': 'form',
                    'res_model': action.res_model,
                    'view_id': form_view_id,
                    'type': 'ir.actions.act_window',
                    'context': context,
                    'target': 'new'
                }
    
            return result

    def print_lot_code(self):
        # for wo in self:
        return self.env['report'].get_action(self, 'product_auto_lot.report_mrp_workorder_lot_code_sheet')


