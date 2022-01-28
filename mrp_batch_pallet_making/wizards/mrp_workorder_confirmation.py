# -*- coding: utf-8 -*-
from odoo import api, models, fields
from odoo.addons import decimal_precision as dp


class AddConfirmMessage(models.TransientModel):
    _name = 'mrp.workorder.confirmation'
    _description = "Confirm Messages"

    qty_production = fields.Float('Original Requested Quantity',
                                  readonly=True)
    current_step = fields.Float('Actual Produced Quantity',
                                readonly=True)
    workorder_id = fields.Many2one('mrp.workorder', 'workorder')

    def button_finish(self):
        self.workorder_id.with_context({'clicked_finish': True}).button_finish()

    @api.model
    def default_get(self, field_list):
        res = super(AddConfirmMessage, self).default_get(field_list)
        if self.env.context.get('active_model', '') != 'mrp.workorder':
            return

        workorder = self.env['mrp.workorder'].browse(self.env.context.get('active_id'))

        res.update({
            'qty_production': workorder.product_qty_per_workcenter,
            'current_step': sum(workorder.mapped('production_id.move_finished_ids.quantity_done')),
            'workorder_id': workorder.id,
        })

        return res
