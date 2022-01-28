# -*- coding: utf-8 -*-

import math
from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT, DEFAULT_SERVER_DATETIME_FORMAT


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    product_qty_per_workcenter = fields.Float(
        'Quantity',
        required=True, states={'done': [('readonly', True)]},
        compute='_get_qty_per_workcenter')
    
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
                    
                    
                    
# There is no move_lot_ids table in odoo14, So skip this method by jana 
#     def post_inventory(self):
#         # Before posting inventory, lets merge all the move lots.
#         for order in self:
#             moves_raw_to_do = order.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
#             for move in moves_raw_to_do:
#                 if move.product_id.tracking != 'none':
#                     move_lots_without_produced_lot = move.mapped('active_move_lot_ids').filtered(lambda x: not x.lot_produced_id and x.quantity_done > 0)
# 
#                     if move_lots_without_produced_lot:
#                         produced_lot_id = move.mapped('active_move_lot_ids.lot_produced_id')
#                         if len(produced_lot_id) != 1:
#                             raise UserError("You must specify a Finished Lot code on the Register Lots screen.")
# 
#                         for move_lot in move_lots_without_produced_lot:
#                             move_lot.lot_produced_id = produced_lot_id[0]
# 
#                     for movelot2merge in move.mapped('active_move_lot_ids'):
#                         if not movelot2merge.exists():
#                             continue
#                         mergable_movelots = move.mapped('active_move_lot_ids').filtered(lambda
#                                                                                             x: x.lot_id == movelot2merge.lot_id and x.lot_produced_id == movelot2merge.lot_produced_id and x != movelot2merge)
#                         movelot2merge.quantity_done += sum(mergable_movelots.mapped('quantity_done'))
#                         mergable_movelots.unlink()
# 
#         return super(MrpProduction, self).post_inventory()

    # @api.multi
    # def _update_raw_move(self, bom_line, line_data):
    #     if self.routing_id.routing_type == 'parallel':
    #         wc_count = len(self.bom_id.routing_id.operation_ids)
    #         quantity = line_data['qty'] / wc_count
    #         self.ensure_one()
    #         move = self.move_raw_ids.filtered(
    #             lambda x: x.bom_line_id.id == bom_line.id and x.state not in ('done', 'cancel'))
    #         if move:
    #             if quantity > 0:
    #                 move[0].write({'product_uom_qty': quantity})
    #             else:
    #                 if move[0].quantity_done > 0:
    #                     raise UserError(_(
    #                         'Lines need to be deleted, but can not as you still have some quantities to consume in them. '))
    #                 move[0].action_cancel()
    #                 move[0].unlink()
    #             return move
    #         else:
    #             self._generate_raw_move(bom_line, line_data)
    #     else:
    #         return super(MrpProduction, self)._update_raw_move(bom_line, line_data)
    #
    # def _generate_raw_move(self, bom_line, line_data):
    #     if self.routing_id.routing_type == 'parallel':
    #         wc_count = len(self.bom_id.routing_id.operation_ids)
    #         quantity = line_data['qty'] / wc_count
    #
    #         # alt_op needed for the case when you explode phantom bom and all the lines will be consumed in the operation given by the parent bom line
    #         alt_op = line_data['parent_line'] and line_data['parent_line'].operation_id.id or False
    #         if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom':
    #             return self.env['stock.move']
    #         if bom_line.product_id.type not in ['product', 'consu']:
    #             return self.env['stock.move']
    #         if self.routing_id:
    #             routing = self.routing_id
    #         else:
    #             routing = self.bom_id.routing_id
    #         if routing and routing.location_id:
    #             source_location = routing.location_id
    #         else:
    #             source_location = self.location_src_id
    #
    #         original_quantity = (self.product_qty - self.qty_produced) or 1.0
    #         data = {
    #             'sequence': bom_line.sequence,
    #             'name': self.name,
    #             'date': self.date_planned_start,
    #             'date_expected': self.date_planned_start,
    #             'bom_line_id': bom_line.id,
    #             'product_id': bom_line.product_id.id,
    #             'product_uom_qty': quantity,
    #             'product_uom': bom_line.product_uom_id.id,
    #             'location_id': source_location.id,
    #             'location_dest_id': self.product_id.property_stock_production.id,
    #             'raw_material_production_id': self.id,
    #             'company_id': self.company_id.id,
    #             'operation_id': bom_line.operation_id.id or alt_op,
    #             'price_unit': bom_line.product_id.standard_price,
    #             'procure_method': 'make_to_stock',
    #             'origin': self.name,
    #             'warehouse_id': source_location.get_warehouse().id,
    #             'group_id': self.procurement_group_id.id,
    #             'propagate': self.propagate,
    #             'unit_factor': quantity / original_quantity,
    #         }
    #         return self.env['stock.move'].create(data)
    #     else:
    #         return super(MrpProduction, self)._generate_raw_move(bom_line, line_data)

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

#     def _workorders_create(self, bom, bom_data):
#         """
#         :param bom: in case of recursive boms: we could create work orders for child
#                     BoMs
#         """
#         workorders = self.env['mrp.workorder']
#         bom_qty = bom_data['qty']
# 
#         # Initial qty producing
#         if self.product_id.tracking == 'serial':
#             quantity = 1.0
#         else:
#             quantity = self.product_qty - sum(self.move_finished_ids.mapped('quantity_done'))
#             quantity = quantity if (quantity > 0) else 0
# 
#         for operation in bom.routing_id.operation_ids:
#             # create workorder
#             cycle_number = math.ceil(bom_qty / operation.workcenter_id.capacity)  # TODO: float_round UP
#             duration_expected = (operation.workcenter_id.time_start +
#                                  operation.workcenter_id.time_stop +
#                                  cycle_number * operation.time_cycle * 100.0 / operation.workcenter_id.time_efficiency)
#             workorder = workorders.create({
#                 'name': operation.name,
#                 'production_id': self.id,
#                 'workcenter_id': operation.workcenter_id.id,
#                 'operation_id': operation.id,
#                 'duration_expected': duration_expected,
#                 'state': len(workorders) == 0 and 'ready' or 'pending',
#                 'qty_producing': quantity,
#                 'capacity': operation.workcenter_id.capacity,
#             })
#             if workorders:
#                 workorders[-1].next_work_order_id = workorder.id
#             workorders += workorder
# 
#             # assign moves; last operation receive all unassigned moves (which case ?)
#             moves_raw = self.move_raw_ids.filtered(lambda move: move.operation_id == operation)
#             if len(workorders) == len(bom.routing_id.operation_ids):
#                 moves_raw |= self.move_raw_ids.filtered(lambda move: not move.operation_id)
#             moves_finished = self.move_finished_ids.filtered(lambda move: move.operation_id == operation) #TODO: code does nothing, unless maybe by_products?
#             moves_raw.mapped('move_lot_ids').write({'workorder_id': workorder.id})
#             (moves_finished + moves_raw).write({'workorder_id': workorder.id})
# 
#             workorder._generate_lot_ids()
#         return workorders
