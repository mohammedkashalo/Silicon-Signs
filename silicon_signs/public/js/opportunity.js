frappe.ui.form.on("Opportunity", {
  sales_stage(frm) {
    
	console.log("sadasdasd")
    if (frm.doc.sales_stage) {


      frappe.db.get_value("Sales Stage", frm.doc.sales_stage, "stage_name")
        .then(r => {
          if (r && r.message) {
			console.log("858552")
            frm.set_value("custom_sales_stage_label", r.message.stage_name);
			console.log("858552lslsl",frm.doc.custom_sales_stage_label)
          }
        });
    } else {
      frm.set_value("custom_sales_stage_label", null);
    }

    if(frm.doc.sales_stage === "On Hold") {
            // Only trigger if no reason yet
            if(!frm.doc.custom_on_hold_reason) {
                let d = new frappe.ui.Dialog({
                    title: "Set On Hold Reason",
                    fields: [
                        {
                            fieldname: "on_hold_reason",
                            fieldtype: "Select",
                            label: "Reason",
                            options: [
                                "Funding",
                                "Client Request",
                                "Other"
                            ],
                            reqd: 1
                        },
                        {
                            fieldname: "other_reason",
                            fieldtype: "Data",
                            label: "Other Reason",
                            depends_on: "eval:doc.on_hold_reason=='Other'"
                        }
                    ],
                    primary_action_label: "Save",
                    primary_action: function(values) {
                        frm.set_value("custom_on_hold_reason", values.on_hold_reason === "Other" ? values.other_reason : values.on_hold_reason);
                        d.hide();
                    }
                });
                d.show();
            }
        }
    
  },

  custom_sales_stage_label(frm) {
	console.log("852")
    if (frm.doc.custom_sales_stage_label) {
      // Look up the matching Sales Stage doc by its name
	  console.log("77777777777777777777")
      frappe.db.get_value("Sales Stage", {"stage_name": frm.doc.custom_sales_stage_label}, "name")
        .then(r => {
          if (r && r.message && r.message.name) {
			console.log("it should work")
            frm.set_value("sales_stage", r.message.name);
          }
        });
    } else {
      frm.set_value("sales_stage", null);
    }
  }
});