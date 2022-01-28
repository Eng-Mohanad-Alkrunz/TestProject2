# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class SaleOrder(models.Model):
    _inherit = "sale.order"

    pickup_date = fields.Datetime('Pickup Date',
                                  help="Pickup date of all deliveries bound for customer. ",
                                  store=True,
                                  inverse = '_set_pickup')

    def _set_pickup(self):
        delivery_pickings = self.picking_ids.filtered(lambda p:
                                                      p.location_dest_id.id ==
                                                      self.env.ref('stock.stock_location_customers').id)\
                                            .sorted(key=lambda p: p.stock_pickup_date, reverse=True)

        for delivery in delivery_pickings:
            if delivery.stock_pickup_date != self.pickup_date:
                delivery.write({'stock_pickup_date': self.pickup_date})
                if delivery.move_lines:
                    for move in delivery.move_lines.filtered(lambda x: x.state not in ['done', 'cancel']):
                        move.write({'stock_pickup_date': self.pickup_date})

    def action_confirm(self):
        super(SaleOrder, self).action_confirm()
        self._set_pickup()
        return True