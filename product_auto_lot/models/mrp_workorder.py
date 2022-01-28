# -*- coding: utf-8 -*-


from datetime import datetime
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare, float_round
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError

class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'
    _order = 'date_planned_start asc'

    gen_date = fields.Datetime('Date of Manufacture') # Legacy, no longer used. Use date_planned_start instead.

    select_lot_ids = fields.Many2many('stock.production.lot', string='Select Lot Codes', store=False, create_edit=False,
                                      help='Select a lot code to add to this workorder.')

    raw_product_ids = fields.Many2many('product.product', compute='_raw_product_ids')



    product_qty_per_workcenter = fields.Float('Quantity to Produce', readonly=True,
                                              related='production_id.product_qty_per_workcenter')

    skip_packing_rules = fields.Boolean('Use Normal Workcenter Rules', default=False)

    #     finished_move_lot_ids = fields.One2many('stock.move.lots', 'workorder_id', domain=lambda self: [('product_id', '!=', self.product_id.id),
    #                                                                                                     ('lot_produced_id', '!=', False),
    #                                                                                                     ('quantity_done', '>', 0),
    #                                                                                                     ('done_wo', '=', True)],
    #                                             string='Finished Lots')

    current_step = fields.Integer('Current Number', default=0, readonly=True)
    time_start = fields.Char('Time', compute="_get_time_start", store=True)
    step_time_start = fields.Datetime('Step Start Time', readonly=True)
    mo_time_start = fields.Datetime('MO Time', store=True, related='production_id.date_planned_start')
    order_active = fields.Boolean(default=False)

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

    def print_lot_code(self):
        # for wo in self:
        return self.env['report'].get_action(self, 'product_auto_lot.report_mrp_workorder_lot_code_sheet')

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
        super(MrpWorkorder, self)._select_lot()
        if self.workcenter_id.workcenter_type in ['batch', 'pallet']:
            lot_ids = self.select_lot_ids
            stock_move = self.env['stock.move']
            for lot in lot_ids:
                stock_move_ids = stock_move.search(
                    [('product_id', '=', lot.product_id.id),
                     ('raw_material_production_id', '=', self.production_id.id)])
                stock_move_ids.write({'last_lot_id': lot._origin.id})

    def action_confirm(self):
        return {
            'name': 'Finish Production',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.workorder.confirmation',
            'view_type': 'form',
            'view_mode': 'form',
            # 'res_id' : new.id
            'target': 'new',
        }

    def record_production(self):
        self.ensure_one()
        #         if any([not x.lot_id and x.quantity_done for x in self.active_move_lot_ids]):
        #             raise ValidationError("Lot codes must be set if there is a quantity greater than zero.")

        if self.workcenter_id.workcenter_type in ['batch', 'pallet'] and not self.skip_packing_rules:
            # Time tracking on packages.
            if not self.production_id.package_ids:
                raise ValidationError("You must generate the packages on the Manufacturing Order before you can begin.")
            current_package = self.production_id.package_ids.filtered(
                lambda x: x.pallet_number == self.current_step + 1)

            if current_package and current_package.start_date and not current_package.end_date:
                # If the current package doesn't have an end_date, we will set it.
                current_package.end_date = datetime.now()
                next_package = self.production_id.package_ids.filtered(
                    lambda x: x.pallet_number == current_package.pallet_number + 1)
                if next_package:
                    next_package.start_date = datetime.now()

            elif current_package and not current_package.start_date and not current_package.end_date:
                # If the current package doesnt have a start date or end date, we'll check for a previous package.
                prev_package = self.production_id.package_ids.filtered(
                    lambda x: x.pallet_number == current_package.pallet_number - 1)
                if prev_package and prev_package.end_date:
                    current_package.end_date = datetime.now()
                    current_package.start_date = prev_package.end_date
                    next_package = self.production_id.package_ids.filtered(
                        lambda x: x.pallet_number == current_package.pallet_number + 1)
                    if next_package:
                        next_package.start_date = datetime.now()

            elif not current_package:
                # If there is no packages found, then we can't continue.
                raise ValidationError("There are no more package left to do.")

            """ END """

            """
                Set the qty_producing to 1, this will cause the move_lots to_do
                to compute to the amounts required to produce 1 qty. This will also 
                make the record_production method only record production of 1 qty, allowing
                you to continue recording more consumption of raw materials.
            """
            self.qty_producing = 1
            lot_id = self.finished_lot_id

            """
                current mo check module by Hoon
            """
            # records = self.env['mrp.workorder'].search([('workcenter_id', '=', self.workcenter_id.id)])
            # for work in records:
            #     work.order_active = False
            # self.order_active = True

            # Execute normal workcenter record_production() method.
            #         res = super(MrpWorkorder, self).record_production()

            self._check_sn_uniqueness()
            self._check_company()
            #         if any(x.quality_state == 'none' for x in self.check_ids):
            #             raise UserError(_('You still need to do the quality checks!'))
            if float_compare(self.qty_producing, 0, precision_rounding=self.product_uom_id.rounding) <= 0:
                raise UserError(
                    _('Please set the quantity you are currently producing. It should be different from zero.'))

            if self.production_id.product_id.tracking != 'none' and not self.finished_lot_id and self.move_raw_ids:
                raise UserError(_('You should provide a lot/serial number for the final product'))

            # Suggest a finished lot on the next workorder
            if self.next_work_order_id and self.product_tracking != 'none' and not self.next_work_order_id.finished_lot_id:
                self.production_id.lot_producing_id = self.finished_lot_id
                self.next_work_order_id.finished_lot_id = self.finished_lot_id
            backorder = False
            # Trigger the backorder process if we produce less than expected
            #         if float_compare(self.qty_producing, self.qty_remaining, precision_rounding=self.product_uom_id.rounding) == -1 and self.is_first_started_wo:
            #             backorder = self.production_id._generate_backorder_productions(close_mo=False)
            #             self.production_id.product_qty = self.qty_producing
            #         else:
            #             if self.operation_id:
            #                 backorder = (self.production_id.procurement_group_id.mrp_production_ids - self.production_id).filtered(
            #                     lambda p: p.workorder_ids.filtered(lambda wo: wo.operation_id == self.operation_id).state not in ('cancel', 'done')
            #                 )[:1]
            #             else:
            #                 index = list(self.production_id.workorder_ids).index(self)
            #                 backorder = (self.production_id.procurement_group_id.mrp_production_ids - self.production_id).filtered(
            #                     lambda p: p.workorder_ids[index].state not in ('cancel', 'done')
            #                 )[:1]

            # Update workorder quantity produced
            #         self.qty_produced = self.qty_producing
            self.qty_produced += self.qty_producing

            # One a piece is produced, you can launch the next work order
            self._start_nextworkorder()
            self.button_finish()

            if backorder:
                for wo in (self.production_id | backorder).workorder_ids:
                    if wo.state in ('done', 'cancel'):
                        continue
                    wo.current_quality_check_id.update(wo._defaults_from_move(wo.move_id))
                    if wo.move_id:
                        wo._update_component_quantity()
                if not self.env.context.get('no_start_next'):
                    if self.operation_id:
                        return backorder.workorder_ids.filtered(
                            lambda wo: wo.operation_id == self.operation_id).open_tablet_view()
                    else:
                        index = list(self.production_id.workorder_ids).index(self)
                        return backorder.workorder_ids[index].open_tablet_view()
            if self.workcenter_id.workcenter_type in ['batch', 'pallet'] and not self.skip_packing_rules:
                self.current_step += 1

                # Set qty_producing to 1, and recompute move_lots
                self.qty_producing = 1
                self._onchange_qty_producing()
                self.step_time_start = ''

                # Bring in the final_lot used in last batch.
                self.finished_lot_id = lot_id and lot_id.id or False
        else:
            res = super(MrpWorkorder, self).record_production()
            return res

        return True

    def call_gen_final_lot(self):
        self.generate_final_lot_code()

    #     def _generate_final_lot_code(self):
    #         for wo in self:
    #             if wo.product_id.lot_abbv and '[USER_DEFINED' in wo.product_id.lot_abbv:
    #                 return wo.action_view_generate_lot_wizard()
    #             else:
    # #                 gen_date = datetime.strptime(self.date_planned_start or fields.Datetime.now(), DEFAULT_SERVER_DATETIME_FORMAT)
    #                 gen_date = self.date_planned_start or fields.Datetime.now()
    #                 lot_name = wo.product_id.gen_lot_code(gen_date=gen_date)
    #                 existing_lots = self.env['stock.production.lot'].search([('name', '=', lot_name), ('product_id', '=', wo.product_id.id)])
    #
    #                 if len(existing_lots.ids) > 0:
    # #                     wo.final_lot_id = existing_lots.ids[0]
    #                     wo.finished_lot_id = existing_lots.ids[0]
    #                 else:
    # #                     wo.final_lot_id = wo.env['stock.production.lot'].create({
    #                     wo.finished_lot_id = wo.env['stock.production.lot'].create({
    #                         'name': lot_name,
    #                         'product_id': wo.product_id.id,
    #                         'gen_date': gen_date,
    #                     }).id
    #                     wo.finished_lot_id.sudo()._use_gen_date()
    #                     wo.final_lot_id.sudo()._use_gen_date()
    #         return True

    #     def write(self, vals):
    #         if vals.get('finished_move_lot_ids') and self.state != 'done':
    #             del vals['finished_move_lot_ids']
    #             if not vals:
    #                 return True
    #         res = super(MrpWorkorder, self).write(vals)
    #         return res