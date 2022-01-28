odoo.define('mrp_batch_pallet_making.RecordProduction', function (require) {
"use strict";

var core = require('web.core');
var Model = require('web.Model');
var Session = require('web.session');
var Dialog = require('web.Dialog');
var FormViewBarcodeHandler = require('barcodes.FormViewBarcodeHandler');
var WorkorderBarcodeHandler = require('mrp_barcode.MrpBarcodeHandler');

var _t = core._t;

function scan_barcode(barcode) {
    odoo.__DEBUG__.services["web.core"].bus.trigger("barcode_scanned", barcode);
}

/*
     This is required because it isn't possible to record_production while in the on_barcode_scanned onchange method.

     This inherited method will call scan_barcode on the mrp.workorder model, and will check for record_production boolean on the response.
*/
FormViewBarcodeHandler.include({
    init: function(parent, context) {
        this.in_mrp_scan = false;
        return this._super.apply(this, arguments);

    },
    on_barcode_scanned: function(barcode) {
        var self = this;

        // Override behavior where the model is mrp.workorder.
        if (self.field_manager.model == 'mrp.workorder') {
            if (self.form_view.get('actual_mode') === 'view') {
                // Make sure user is in Edit Mode.
                this._display_no_edit_mode_warning();
            } else {

                if (self.in_mrp_scan == false) {
                    self.in_mrp_scan = true;
                    self.mrp_model = new Model('mrp.workorder');
                    // Send barcode to custom scan_barcode method.
                    self.view.save().then(function(result){
                        return self.mrp_model.call('scan_barcode',  [[self.form_view.datarecord.id], barcode]).then(function (result) {
                            // If the result has a record_production boolean that is true, then call record_production.
                            if ((result) && (result.record_production == true)) {
                                self.mrp_model.call('record_production', [[self.form_view.datarecord.id]]).then(function (result) {
                                    // Then reload the view.
                                    self.view.reload();
                                    self.in_mrp_scan = false;
                                }).fail(function() {
                                    self.in_mrp_scan = false;
                                });;
                            } else {
                                self.view.reload();
                                self.in_mrp_scan = false;
                            }
                        }).fail(function() {
                            self.in_mrp_scan = false;
                        });
                    });
                }

            }

        } else {
            self._super(barcode);
        }
    },
});
});
