# -*- coding: utf-8 -*-


from datetime import datetime
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.addons import decimal_precision as dp

class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'
    
    production_id = fields.Many2one("mrp.production", string="Production")

class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    package_ids = fields.One2many('stock.quant.package', 'production_id', string='Related Packages', copy=False)
    palletize_ready = fields.Boolean('Ready to Palletize', compute='_ready_to_palletize')

    product_qty_per_workcenter = fields.Float(
        'Quantity',
        required=True, states={'done': [('readonly', True)]},
        compute='_get_qty_per_workcenter')

    # QoL improvement
    sequence_step = fields.Selection([
        ('even_odd', 'Even/Odd'),
        ('serial', 'Serial')], 'Sequence Step',
        required=False,
        help='When using Even or Odd, make sure the '
             'starting pallet number is even or odd number.')

    picking_ids = fields.Many2many('stock.picking', string='Pickings', compute='_get_pickings')

    def _get_pickings(self):
        for mo in self:
            pickings = self.env['stock.picking'].search([('group_id', '=', mo.procurement_group_id.id)])
            mo.picking_ids = [(6, 0, pickings.ids)]

#     @api.onchange('bom_id')
#     def onchange_bom_id(self):
#         """ Find the picking type. """
#         if self.bom_id and self.bom_id.picking_type_id:
#             self.picking_type_id = self.bom_id.picking_type_id.id

#     @api.multi
    def _ready_to_palletize(self):
        for rec in self:
#             picking_line_ids = rec.picking_ids.filtered(lambda x:
#                                                     x.picking_type_id.id == rec.picking_type_id.warehouse_id.manu_packing_type_id.id
#                                                     and x.state not in ['done', 'cancel']).mapped('pack_operation_product_ids').filtered(lambda x:
#                                                                                          x.product_id.id == rec.product_id.id
#                                                                                          and x.result_package_id.id is False)
            picking_line_ids = rec.picking_ids.filtered(lambda x:
                                                    x.picking_type_id.id == rec.picking_type_id.warehouse_id.manu_packing_type_id.id
                                                    and x.state not in ['done', 'cancel']).mapped('move_line_ids_without_package').filtered(lambda x:
                                                                                         x.product_id.id == rec.product_id.id
                                                                                         and x.result_package_id.id is False)
                                                    
            if len(picking_line_ids) > 0:
                rec.palletize_ready = True
            else:
                rec.palletize_ready = False

    def action_palletize(self):
        packing_picking_ids = self.picking_ids.filtered(lambda x: x.picking_type_id.id == self.picking_type_id.warehouse_id.manu_packing_type_id.id
                                                   and x.state not in ['done', 'cancel'])

        for picking in packing_picking_ids:
#             for pack_op in picking.pack_operation_product_ids:
            for pack_op in picking.move_line_ids_without_package:
#                 for pack_lot in pack_op.pack_lot_ids:
#                     pack_lot.qty = pack_lot.qty_todo
#                 pack_op.qty_done = pack_op.product_qty
                pack_op.qty_done = pack_op.product_uom_qty
            picking.do_new_transfer(from_code=True)
            
            
#     @api.multi
    def action_create_packages(self):
        
        self.ensure_one()
        
        action = self.env.ref('product_auto_lot.action_view_generate_pallet_code_wizard')
        form_view_id = self.env.ref('product_auto_lot.view_generate_pallet_code_wizard').id
        context = dict(self.env.context or {})
        context['default_production_id'] = self.id
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
            lot_id = self.env['stock.production.lot'].search(
                [('name', '=', lot_code), ('product_id', '=', self.product_id.id)])

            if lot_id:
                packages = self.env['stock.quant.package'].search(
                    [('default_lot_code_id', '=', lot_id.id), ('end_date', '=', False)])
                if not packages:
                    raise UserError("No packages were found.")

                if packages:
                    packages.write({'production_id': self.id})
                    current_step = packages.sorted(key=lambda r: r.pallet_number)[0].pallet_number - 1
                    self.workorder_ids.write({'finished_lot_id': packages[0].default_lot_code_id.id})
                    if current_step > 0:
                        self.workorder_ids.write({'current_step': current_step})

