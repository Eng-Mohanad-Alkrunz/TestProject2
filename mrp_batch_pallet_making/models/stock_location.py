# -*- coding: utf-8 -*-

from odoo import models, fields, api, SUPERUSER_ID
from odoo.tools import float_compare, float_round, float_is_zero
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)


class StockLocation(models.Model):
    _inherit = 'stock.location'
    
# Below function will be used in odoo14, since produced_quant_ids is not availble in odoo14 and there is no field to update
#     def action_repair_quant_tracing(self):
#         self.ensure_one()
#         # Do nothing if current user isnt the super user.
#         if self.env.uid != SUPERUSER_ID:
#             raise UserError('Only the superuser may use this button.')
#         if self.usage != 'production':
#             raise UserError('Can only be run on the Production location.')
#         quant_obj = self.env['stock.quant']
#         quants_to_repair = quant_obj.search([('location_id', '=', self.id),
#                                              ('lot_id', '!=', False),
#                                              ('produced_quant_ids', '=', False)])
# 
#         for quant in quants_to_repair:
#             move_id = quant.history_ids.filtered(lambda x: x.raw_material_production_id and x.location_dest_id == quant.location_id)
#             production_id = move_id.mapped('raw_material_production_id')
# 
#             if not move_id or not production_id:
#                 _logger.info("%s|%s: Skipping quant because it has no MO." % (quant.id, quant.lot_id.name))
#                 continue
# 
#             if move_id.mapped('location_dest_id') != quant.location_id:
#                 raise UserError('Location mismatch.')
# 
#             if len(production_id) > 1:
#                 raise UserError('Too many production orders')
# 
#             produced_quant_ids = move_id.mapped('quant_ids.produced_quant_ids')
# 
#             if not produced_quant_ids:
#                 _logger.info("%s|%s|%s: There were no produced quants found." % (quant.id, quant.lot_id.name, production_id.name))
#                 continue
# 
#             quant.sudo().write({'produced_quant_ids': [(4, quant.id) for quant in produced_quant_ids]})
# 
#             move_lots_to_update = move_id.mapped('active_move_lot_ids').filtered(lambda x: not x.lot_produced_id)
#             for move_lot in move_lots_to_update:
#                 move_lot.lot_produced_id = produced_quant_ids[0].lot_id
# 
#             _logger.info("%s|%s|%s: Repaired link to %s produced Stock Quants." % (quant.id, quant.lot_id.name, production_id.name, str(len(produced_quant_ids.ids))))
# 
#         quants_to_repair.aggressive_merge_stock_quants()
# 
#         return True


