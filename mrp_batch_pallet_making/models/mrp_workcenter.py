# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime


class ChangeMrpWorkCenterSettingsUi(models.Model):
    _inherit = 'mrp.workcenter'

    workcenter_type = fields.Selection([('normal', 'Normal UI'),
                                        ('batch', 'Batch Making UI'),
                                        ('pallet', 'Pallet Making UI')], default='normal')
    
    lot_abbv = fields.Char('Lot Code', help='This value will be used in lot code generation where \n'
                                            '[WORKCENTER_CODE] is defined.')

    def button_show_workorders(self):
        self.ensure_one()
        action = self.env.ref('mrp.action_work_orders')
        if self.workcenter_type == 'batch':
            form_view_id = self.env.ref('mrp_batch_pallet_making.mrp_batch_ui').id

        elif self.workcenter_type == 'pallet':
            form_view_id = self.env.ref('mrp_batch_pallet_making.mrp_pallet_ui').id
        else:
            form_view_id = self.env.ref('mrp.mrp_production_workorder_form_view_inherit').id
            result = {
                'name': _(action.name),
                'help': action.help,
                'view_mode': 'kanban,tree,calendar,pivot,graph',
                'res_model': action.res_model,
#                 'view_id': form_view_id,
                'views': [(False, 'tree'), (False, 'gantt'), (False, 'pivot'), (False, 'graph'),
                    (False, 'calendar')],
                'type': 'ir.actions.act_window',
                'context': action.context,
                'domain': action.domain,
                'target': action.target,
            }
        
            return result

#          {
#             'name': action.name,
#             'help': action.help,
# #             'mode': action.model,
#             'views': [(False, 'tree'), (False, 'form'), (False, 'gantt'), (False, 'pivot'), (False, 'graph'),
#                       (False, 'calendar')],
#             'view_mode': 'kanban,tree,form,calendar,pivot,graph',
#             'target': action.target,
#             'context': action.context,
#             'domain': action.domain,
#             'res_model': action.res_model,
#             'active_id': self.id
#         }
        
        result = {
                'name': _(action.name),
                'help': action.help,
                'view_mode': 'kanban,tree,form,calendar,pivot,graph',
                'res_model': action.res_model,
#                 'view_id': form_view_id,
                'views': [(False, 'tree'), (form_view_id, 'form'), (False, 'gantt'), (False, 'pivot'), (False, 'graph'),
                    (False, 'calendar')],
                'type': 'ir.actions.act_window',
                'context': action.context,
                'domain': action.domain,
                'target': action.target,
            }
        
        return result
    
    
    
    def button_final_lot_code(self):
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
        return True
    

    def button_show_workorders_mobile(self):
        self.ensure_one()
        action = self.env.ref('mrp_workorder.mrp_workorder_action_tablet')

        if self.workcenter_type == 'batch':
            form_view_id = self.env.ref('mrp_batch_pallet_making.mrp_batch_ui').id
        elif self.workcenter_type == 'pallet':
            form_view_id = self.env.ref('mrp_batch_pallet_making.mrp_pallet_ui').id
        else:
            form_view_id = self.env.ref('mrp.mrp_production_workcenter_form_view_inherit').id

        return {
            'name': action.name,
            'help': action.help,
            'mode': action.mode,
            'views': [(self.env.ref('mrp.workcenter_line_kanban').id, 'kanban'), (self.env.ref('mrp.mrp_production_workcenter_tree_view_inherit').id, 'tree'), (form_view_id, 'form'),],
            'view_mode': 'kanban,tree,form,calendar,pivot,graph',
            'target': 'fullscreen',
            'context': action.context,
            'domain': action.domain,
            'res_model': action.res_model,
            'active_id': self.id
        }
