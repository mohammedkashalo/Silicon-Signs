frappe.ui.form.on('Quotation', {
    refresh: function(frm) {
        frm.add_custom_button(__('Configure Signss'), function() {
            // Open the popup for the Sign Configuration doctype
            var dialog = new frappe.ui.Dialog({
                title: __('Sign Configuration'),
                fields: [
                    {
                        label: 'Sign Type',
                        fieldname: 'sign_type',
                        fieldtype: 'Link',
                        options: 'Item Group',
                        reqd: 1
                    },
                    {
                        label: 'Lighting Type',
                        fieldname: 'lighting_type',
                        fieldtype: 'Select',
                        options: ['Face-lit', 'Reverse Halo', 'Other'],
                        reqd: 1
                    },
                    {
                        label: 'Mounting Type',
                        fieldname: 'mounting_type',
                        fieldtype: 'Select',
                        options: ['Raceway', 'Flush', 'Other'],
                        reqd: 1
                    },
                    {
                        label: 'Quantity',
                        fieldname: 'quantity',
                        fieldtype: 'Float',
                        reqd: 1
                    },
                    {
                        label: 'Perimeter Inches',
                        fieldname: 'perimeter_inches',
                        fieldtype: 'Float',
                        reqd: 1
                    },
                    {
                        label: 'LED Count',
                        fieldname: 'led_count',
                        fieldtype: 'Int',
                        reqd: 1
                    },
                    {
                        label: 'Sheet Count',
                        fieldname: 'sheet_count',
                        fieldtype: 'Float',
                        reqd: 1
                    },
                    {
                        label: 'Paint Returns',
                        fieldname: 'paint_returns',
                        fieldtype: 'Check',
                    },
                    {
                        label: 'Vinyl Printed',
                        fieldname: 'vinyl_printed',
                        fieldtype: 'Check',
                    }
                ],
                primary_action_label: __('Save'),
                primary_action: function() {
                    // Create a new Sign Configuration record
                    frappe.call({
                        method: 'frappe.client.save',
                        args: {
                            doc: {
                                doctype: 'Sign Configuration',
                                sign_type: dialog.get_value('sign_type'),
                                lighting_type: dialog.get_value('lighting_type'),
                                mounting_type: dialog.get_value('mounting_type'),
                                quantity: dialog.get_value('quantity'),
                                perimeter_inches: dialog.get_value('perimeter_inches'),
                                led_count: dialog.get_value('led_count'),
                                sheet_count: dialog.get_value('sheet_count'),
                                paint_returns: dialog.get_value('paint_returns'),
                                vinyl_printed: dialog.get_value('vinyl_printed')
                            }
                        },
                        callback: function(response) {
                            frappe.msgprint(__('Sign Configuration added successfully.'));
                            dialog.hide();
                        }
                    });
                }
            });
            dialog.show();
        });
    }
});