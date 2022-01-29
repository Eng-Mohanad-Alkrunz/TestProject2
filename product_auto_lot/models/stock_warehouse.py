# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

from datetime import datetime

from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_round, float_compare
from odoo import models, exceptions, fields, api, _

class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    manufacture_and_pack = fields.Boolean('Packaging Step after Manufacturing',
                                          help='Enable Manufacture and Pack route.')

    wh_mrp_pack_stock_loc_id = fields.Many2one('stock.location', 'Manufacturing Packaging Location',
                                               help='Location where packaging occurs after manufacturing operations.')

    manu_packing_type_id = fields.Many2one('stock.picking.type', 'Manufacturing Packaging Picking Type',
                                           help='Picking type for packaging operations from manufacturing.')
    manufacture_pack_pull_id = fields.Many2one('stock.rule', 'Manufacture rule from Make and Pack')
    manufacture_packing_pull_id = fields.Many2one('stock.rule', 'Pack Rule for Make and Pack')
    manufacture_packing_push_id = fields.Many2one('stock.rule', 'Packing Push Rule')

    def _mrp_pack_stock_location(self):
        mrp_pack_loc = self.env['stock.location'].search([('name', '=', _('Palletizing')),
                                                          ('location_id', '=', self.view_location_id.id)])
        if len(mrp_pack_loc) > 0:
            return mrp_pack_loc.id
        else:
            return self.env['stock.location'].with_context(active_test=False).create({
                'name': _('Palletizing'),
                'active': True,
                'usage': 'internal',
                'location_id': self.view_location_id.id,
                'company_id': self.company_id.id
            }).id

    def _enable_all_packing_operations(self):
        for warehouse in self:
            picking_type_ids = self.env['stock.picking.type'].search([('warehouse_id', '=', warehouse.id)])
            for picking_type in picking_type_ids:
                picking_type.show_entire_packs = True

    def _create_manufacturing_packaging_picking_type(self):
        picking_type_obj = self.env['stock.picking.type']
        seq_obj = self.env['ir.sequence']
        for warehouse in self:
            mrp_packing_seq_id = seq_obj.sudo().create(
                {'name': warehouse.name + _(' Sequence Manufacturing Palletizing'),
                 'prefix': warehouse.code + '/PALLET/',
                 'padding': 4})

            other_pick_type = picking_type_obj.search([('warehouse_id', '=', warehouse.id)], order='sequence desc',
                                                      limit=1)
            color = other_pick_type and other_pick_type.color or 0
            max_sequence = other_pick_type and other_pick_type.sequence or 0

            manu_packing_type = picking_type_obj.create({
                'name': _('Palletizing'),
                'warehouse_id': warehouse.id,
                'code': 'internal',
                'sequence_code': 'MP',
                'show_entire_packs': True,
                'use_create_lots': False,
                'use_existing_lots': True,
                'sequence_id': mrp_packing_seq_id.id,
                'default_location_src_id': warehouse.wh_mrp_pack_stock_loc_id.id,
                'default_location_dest_id': warehouse.lot_stock_id.id,
                'sequence': max_sequence,
                'color': color})

            warehouse.write({
                'manu_packing_type_id': manu_packing_type.id,
            })

    def get_rules_dict(self):
        result = super(StockWarehouse, self).get_rules_dict()
        for warehouse in self:
            result[warehouse.id].update({
                'manufacture_pack': [
                    self.Routing(warehouse.lot_stock_id, warehouse.lot_stock_id, warehouse.int_type_id, 'pull')
                ],
            })
        return result

    def _get_manufacture_pack_route_id(self):
        manufacture_pack_route_id = self.env.ref('mrp_packing_pallatize.route_warehouse0_manufacture_palletize').id
        if not manufacture_pack_route_id:
            manufacture_pack_route_id = self.env['stock.location.route'].search(
                [('name', 'like', _('Manufacture and Palletize'))], limit=1).id
        if not manufacture_pack_route_id:
            raise exceptions.UserError(_('Can\'t find any generic Manufacture and Package route.'))
        return manufacture_pack_route_id

    def _get_manufacture_pack_pull_rules_values(self):
        route_id = self._get_manufacture_pack_route_id()
        if not self.manu_type_id:
            self._create_manufacturing_picking_type()
        if not self.wh_mrp_pack_stock_loc_id:
            self.wh_mrp_pack_stock_loc_id = self._mrp_pack_stock_location()
        if not self.manu_packing_type_id:
            self._create_manufacturing_packaging_picking_type()
        manufacture_palletizing_pull_id = {'name': self._format_routename(_('Manufacture -> Palletizing')),
                                           'procure_method': 'mts_else_mto',
                                           'company_id': self.company_id.id,
                                           'action': 'pull',
                                           'auto': 'manual',
                                           'route_id': route_id,
                                           'location_id': self.wh_mrp_pack_stock_loc_id.id,
                                           'location_src_id': self.lot_stock_id.id,
                                           'picking_type_id': self.manu_type_id.id
                                           }
        palletizing_stock_push_id = {'name': self._format_routename(_('Palletizing -> Stock')),
                                     'procure_method': 'make_to_stock',
                                     'company_id': self.company_id.id,
                                     'action': 'push',
                                     'auto': 'manual',
                                     'route_id': route_id,
                                     'location_id': self.lot_stock_id.id,
                                     'location_src_id': self.wh_mrp_pack_stock_loc_id.id,
                                     'picking_type_id': self.manu_packing_type_id.id,
                                     }
        rules = [manufacture_palletizing_pull_id, palletizing_stock_push_id]

        return rules

    def _get_manufacture_route_id(self):
        manufacture_route = self.env.ref('mrp.route_warehouse0_manufacture', raise_if_not_found=False)
        if not manufacture_route:
            manufacture_route = self.env['stock.location.route'].search([('name', 'like', _('Manufacture'))], limit=1)
        if not manufacture_route:
            raise exceptions.UserError(_('Can\'t find any generic Manufacture route.'))
        return manufacture_route.id

    def _get_manufacture_pack_push_rules_values(self):
        if not self.manu_type_id:
            self._create_manufacturing_picking_type()
        if not self.wh_mrp_pack_stock_loc_id:
            self.wh_mrp_pack_stock_loc_id = self._mrp_pack_stock_location()
        if not self.manu_packing_type_id:
            self._create_manufacturing_packaging_picking_type()
        route_id = self._get_manufacture_route_id()
        # TODO: Setup PUSH rule on manufacturing route.
        # Procure/Move pallets from palletizing to stock
        palletizing_stock = {
            'name': self._format_routename(_('Palletizing -> Stock')),
            'procure_method': 'make_to_stock',
            'location_src_id': self.wh_mrp_pack_stock_loc_id.id,  # TDE FIXME
            'location_id': self.lot_stock_id.id,
            'action': 'pull_push',
            'route_id': route_id,
            'auto': 'manual',
            'picking_type_id': self.manu_packing_type_id.id,
            'company_id': self.company_id.id,
            # 'propagate': True,
            'active': True,
        }
        # return vals for use in write/create methods.
        rule = [palletizing_stock]
        return rule

    def _create_or_update_manufacture_pack_pull(self, routes_data):
        routes_data = routes_data or self.get_routes_dict()
        for warehouse in self:
            mrp_pack_routings = routes_data[warehouse.id]['manufacture_pack']
            mrp_routings = routes_data[warehouse.id]['one_step']
            mrp_pull_rules = warehouse._get_manufacture_pack_pull_rules_values()
            mrp_push_rules = warehouse._get_manufacture_pack_push_rules_values()
            if warehouse.manufacture_pack_pull_id and warehouse.manufacture_packing_push_id:
                manufacture_pull = warehouse.manufacture_pack_pull_id
                manufacture_push = warehouse.manufacture_packing_push_id
                for rule in mrp_pull_rules:
                    manufacture_pull.write(rule)
                for rule in mrp_push_rules:
                    manufacture_push.write(rule)
            else:
                manufacture_pull = []
                manufacture_push = []
                for rule in mrp_pull_rules:
                    print(rule)
                    stock_rule = self.env['stock.rule'].create(rule)
                    manufacture_pull.append(stock_rule)
                for rule in mrp_push_rules:
                    push_rule = self.env['stock.rule'].create(rule)
                    manufacture_push.append(push_rule)
        return manufacture_pull, manufacture_push

    @api.model
    def create(self, vals):
        warehouses = super(StockWarehouse, self).create(vals)
        if 'manufacture_and_pack' in vals:
            if vals.get("manufacture_and_pack"):
                for warehouse in warehouses.filtered(lambda warehouse: not warehouse.manufacture_pack_pull_id):
                    warehouse.wh_mrp_pack_stock_loc_id = warehouse._mrp_pack_stock_location()
                    manufacture_pull, manufacture_push = warehouse._create_or_update_manufacture_pack_pull(
                        warehouse.get_rules_dict())
                    # manufacture_push = warehouse._create_or_update_manufacture_pack_pull(warehouse.get_routes_dict())
                    warehouse.manufacture_pack_pull_id = next(
                        (x.id for x in manufacture_pull if x.action == 'manufacture'),
                        None)
                    warehouse.manufacture_packing_pull_id = next((x.id for x in manufacture_pull if x.action == 'move'),
                                                                 None)
                    warehouse.manufacture_packing_push_id = next((x.id for x in manufacture_push if x.auto == 'move'),
                                                                 None)
                for warehouse in warehouses:
                    if not warehouse.manu_packing_type_id:
                        warehouse._create_manufacturing_packaging_picking_type()
                        warehouse.manu_packing_type_id.active = True
                warehouses._enable_all_packing_operations()
                warehouse.manu_type_id.write({
                    'default_location_dest_id': warehouse.wh_mrp_pack_stock_loc_id.id})
            else:
                for warehouse in warehouses:
                    if warehouse.manu_packing_type_id:
                        warehouse.manu_packing_type_id.active = False
        return warehouses

    def write(self, vals):
        if vals.get('wh_mrp_pack_stock_loc_id') and len(vals) == 1:
            return super(StockWarehouse, self).write(vals)
        if 'manufacture_to_resupply' in vals:
            if vals.get('manufacture_to_resupply') is False:
                vals['manufacture_and_pack'] = False
        if 'manufacture_and_pack' in vals:
            for warehouse in self.filtered(lambda warehouse: not warehouse.manufacture_pack_pull_id):
                manufacture_pull, manufacture_push = warehouse._create_or_update_manufacture_pack_pull(
                    self.get_rules_dict())
                print(manufacture_pull, manufacture_push)
                vals['manufacture_pack_pull_id'] = next((x.id for x in manufacture_pull if x.action == 'manufacture'),
                                                        None)
                vals['manufacture_packing_pull_id'] = next((x.id for x in manufacture_pull if x.action == 'pull'), None)
                vals['manufacture_packing_push_id'] = next((x.id for x in manufacture_push if x.action == 'push'), None)
                for warehouse in self:
                    if not warehouse.manu_packing_type_id:
                        warehouse._create_manufacturing_packaging_picking_type()
                    warehouse.manu_packing_type_id.active = True
                    # Update manufacturing picking to use palletizing as destination.
                    warehouse.manu_type_id.write({
                        'default_location_dest_id': warehouse.wh_mrp_pack_stock_loc_id.id})
                self._enable_all_packing_operations()
        else:
            for warehouse in self:
                if warehouse.manu_packing_type_id:
                    warehouse.manu_packing_type_id.active = False
                warehouse.manu_type_id.write({
                    'default_location_dest_id': warehouse.lot_stock_id.id})
            self.mapped('manufacture_pack_pull_id').unlink()
            self.mapped('manufacture_packing_pull_id').unlink()
            self.mapped('manufacture_packing_push_id').unlink()
        return super(StockWarehouse, self).write(vals)


    lot_abbv = fields.Char('Lot Code', help='This value will be used in lot code generation where \n'
                                            '[WAREHOUSE_CODE] is defined.')

