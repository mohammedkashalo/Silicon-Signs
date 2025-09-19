frappe.ui.form.on('Quotation', {
    refresh: function (frm) {
        frm.add_custom_button(__('Configure Sign'), function () {
            // Open the popup for the Sign Configuration doctype
            var dialog = new frappe.ui.Dialog({
                title: __('Sign Configuration'),
                fields: [
                    {
                        label: 'Sign Template',
                        fieldname: 'sign_template',
                        fieldtype: 'Link',
                        options: 'Item',
                        reqd: 1,
                        link_filters: {
                            "has_variants": 1  // Only fetch items where has_variants = 1
                        }
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
                primary_action: function () {
                    // Create a new Sign Configuration record
                    var data = dialog.get_values();
                    var template = dialog.get_value("sign_template");
                    console.log("data before removing fields:", data);

                    
                    // Remove the unwanted fields
                    delete data.vinyl_printed;
                    delete data.paint_returns;
                    delete data.sign_template;

                    console.log("data after removing fields:", data);
                    var base_price = 100; // Example base price
                    var price = base_price;

                    // Add logic to calculate the price based on the configuration
                    price += data.perimeter_inches * 10;  // Example: Add price based on perimeter inches
                    price += data.led_count * 5;  // Example: Add price based on LED count
                    price += data.sheet_count * 20;  // Example: Add price based on sheet count

                    console.log("Calculated price:", price);

                    // Call get_variant to check if the variant already exists
                    frappe.call({
                        method: "erpnext.controllers.item_variant.get_variant",
                        args: {
                            template: template, // Pass the selected template
                            args: data           // Pass the configuration data
                        },
                        callback: function(response) {
                            // Handle the response for getting the variant (if needed)
                            console.log("get_variant response:", response);
                        }
                    });

                    // Call create_variant to create a new item variant
                    frappe.call({
                        method: "erpnext.controllers.item_variant.create_variant",
                        args: {
                            item: template,  // Pass the selected template item
                            args: data       // Pass the configuration data
                        },
                        callback: function(response) {
                            // Handle the response for creating the variant
                            console.log("create_variant response:", response);
                            frappe.msgprint(__('New item variant created successfully.'));
                            dialog.hide()
                        }
                    });
                }
            });
            dialog.show();
        });
    }
});
