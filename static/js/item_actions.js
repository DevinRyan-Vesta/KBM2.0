(() => {
  const config = window.kbmItemDetails || null;
  const modalRoot = document.getElementById("item-action-modal");

  if (!config || !modalRoot) {
    return;
  }

  const modalForm = modalRoot.querySelector("#item-action-modal-form");
  const modalTitle = modalRoot.querySelector("#item-action-modal-title");
  const modalBody = modalRoot.querySelector("#item-action-modal-body");
  const modalSubmitBtn = modalRoot.querySelector("#item-action-modal-submit");

  const {
    itemType,
    statusOptions = [],
    statusOptionsLower = [],
    propertyOptions = [],
    propertyMap = {},
    propertyUnits = {},
    pieceTypes = [],
    conditionOptions = [],
    availableCopies = 0,
    activeCheckoutsUrl = null,
  } = config;

  const resolvedStatusOptions = Array.isArray(statusOptionsLower) && statusOptionsLower.length
    ? statusOptionsLower
    : statusOptions;

  let submitHandler = null;

  function friendlyLabel(value) {
    return String(value || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (match) => match.toUpperCase());
  }

  function buildOptions(selectEl, options) {
    selectEl.innerHTML = "";
    (options || []).forEach((option) => {
      let value;
      let label;
      if (Array.isArray(option)) {
        [value, label] = option;
      } else if (typeof option === "object" && option !== null) {
        value = option.value ?? option.id ?? "";
        label = option.label ?? option.display ?? option.name ?? option.text ?? value;
      } else {
        value = option;
        label = option;
      }
      const opt = document.createElement("option");
      opt.value = value != null ? String(value) : "";
      opt.textContent = label != null ? String(label) : "";
      selectEl.appendChild(opt);
    });
  }

  function createField(field) {
    const wrapper = document.createElement("div");
    wrapper.className = "modal-field";

    if (field.label) {
      const label = document.createElement("label");
      label.setAttribute("for", `modal-${field.name}`);
      label.textContent = field.label;
      wrapper.appendChild(label);
    }

    let control;
    if (field.widget === "select") {
      control = document.createElement("select");
      control.id = `modal-${field.name}`;
      control.name = field.name;
      buildOptions(control, field.options || []);
      if (field.defaultValue !== undefined) {
        control.value = String(field.defaultValue ?? "");
      }
      control.dataset.defaultValue = control.value || "";
    } else if (field.type === "textarea") {
      control = document.createElement("textarea");
      control.id = `modal-${field.name}`;
      control.name = field.name;
      control.rows = field.rows || 3;
      control.value = field.defaultValue != null ? String(field.defaultValue) : "";
    } else {
      control = document.createElement("input");
      control.id = `modal-${field.name}`;
      control.name = field.name;
      control.type = field.type || "text";
      if (field.min !== undefined) {
        control.min = field.min;
      }
      if (field.max !== undefined) {
        control.max = field.max;
      }
      if (field.step !== undefined) {
        control.step = field.step;
      }
      control.value = field.defaultValue != null ? String(field.defaultValue) : "";
    }

    if (field.placeholder) {
      control.placeholder = field.placeholder;
    }
    if (field.required) {
      control.required = true;
    }
    if (field.autocomplete) {
      control.autocomplete = field.autocomplete;
    } else if (field.type === "date") {
      control.autocomplete = "off";
    }

    wrapper.appendChild(control);

    if (field.help) {
      const helper = document.createElement("small");
      helper.className = "muted text-small";
      helper.textContent = field.help;
      wrapper.appendChild(helper);
    }

    return wrapper;
  }

  function resetModal() {
    modalTitle.textContent = "Action";
    modalSubmitBtn.textContent = "Submit";
    modalBody.innerHTML = "";
    submitHandler = null;
  }

  function closeModal() {
    modalRoot.classList.remove("show");
    document.body.classList.remove("modal-open");
    resetModal();
    modalForm.reset();
  }

  function openModal({ title, submitLabel, fields, onSubmit }) {
    resetModal();
    if (title) {
      modalTitle.textContent = title;
    }
    if (submitLabel) {
      modalSubmitBtn.textContent = submitLabel;
    }
    (fields || []).forEach((field) => {
      modalBody.appendChild(createField(field));
    });
    submitHandler = onSubmit || null;
    modalRoot.classList.add("show");
    document.body.classList.add("modal-open");
    const firstField = modalBody.querySelector("input, select, textarea");
    if (firstField) {
      firstField.focus();
    }

    const propertySelect = modalBody.querySelector("#modal-property_id");
    const unitSelect = modalBody.querySelector("#modal-property_unit_id");
    if (propertySelect && unitSelect) {
      const propertyDefault = propertySelect.dataset.defaultValue || propertySelect.value || "";
      const unitDefault = unitSelect.dataset.defaultValue || unitSelect.value || "";
      configurePropertyUnitHandler(propertySelect, unitSelect, propertyDefault, unitDefault);
    }
  }

  function computeNextUrl(redirectUrl, redirectAnchor) {
    const base = redirectUrl && redirectUrl !== "#" ? redirectUrl : window.location.href;
    if (!redirectAnchor) {
      return base;
    }
    const hashless = base.split("#")[0];
    return `${hashless}#${redirectAnchor}`;
  }

  function submitAction(url, payload, redirectUrl, redirectAnchor) {
    if (!url || url === "#") {
      return;
    }
    const form = document.createElement("form");
    form.method = "post";
    form.action = url;

    // Add CSRF token
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
    if (csrfToken) {
      const csrfInput = document.createElement("input");
      csrfInput.type = "hidden";
      csrfInput.name = "csrf_token";
      csrfInput.value = csrfToken;
      form.appendChild(csrfInput);
    }

    Object.entries(payload || {}).forEach(([key, value]) => {
      const input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = value != null ? String(value) : "";
      form.appendChild(input);
    });

    const nextValue = computeNextUrl(redirectUrl, redirectAnchor);
    if (nextValue) {
      const nextInput = document.createElement("input");
      nextInput.type = "hidden";
      nextInput.name = "next";
      nextInput.value = nextValue;
      form.appendChild(nextInput);
    }

    document.body.appendChild(form);
    form.submit();
  }

  function getUnitOptions(propertyId) {
    const units = propertyUnits[propertyId] || [];
    return [["", "-- None --"]].concat(units.map((unit) => [unit.id, unit.label]));
  }

  function configurePropertyUnitHandler(propertySelect, unitSelect, defaultPropertyId, defaultUnitId) {
    const applyOptions = (propertyId, unitId) => {
      const options = getUnitOptions(propertyId);
      buildOptions(unitSelect, options);
      unitSelect.value = unitId || "";
      const wrapper = unitSelect.closest(".modal-field");
      if (wrapper) {
        const hasUnits = (propertyUnits[propertyId] || []).length > 0;
        wrapper.style.display = hasUnits ? "" : "none";
      }
    };

    applyOptions(defaultPropertyId || propertySelect.value || "", defaultUnitId || "");

    propertySelect.addEventListener("change", () => {
      applyOptions(propertySelect.value || "", "");
    });
  }

  modalForm.addEventListener("submit", (event) => {
    event.preventDefault();
    if (typeof submitHandler === "function") {
      const result = submitHandler(new FormData(modalForm));
      if (result === false) {
        return;
      }
    }
    closeModal();
  });

  modalRoot.querySelectorAll("[data-modal-cancel]").forEach((trigger) => {
    trigger.addEventListener("click", () => closeModal());
  });

  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modalRoot.classList.contains("show")) {
      closeModal();
    }
  });

  function handleCheckout(button) {
    const actionUrl = button.dataset.action;
    if (!actionUrl || actionUrl === "#") {
      return;
    }
    const label = button.dataset.label || "item";
    const redirectUrl = button.dataset.redirect;
    const redirectAnchor = button.dataset.redirectAnchor;
    const datasetLocation = button.dataset.location || "";
    const datasetAddress = button.dataset.address || "";
    const datasetAssigned = button.dataset.assigned || "";
    const available = parseInt(button.dataset.available || availableCopies, 10) || 0;

    if (itemType === "lockbox") {
      openModal({
        title: `Check Out ${label}`,
        submitLabel: "Check Out",
        fields: [
          { name: "code", label: "Current Code", required: true },
          { name: "assigned_to", label: "Assign To", defaultValue: datasetAssigned, placeholder: "Optional" },
          { name: "location", label: "Location", defaultValue: datasetLocation, placeholder: "Optional" },
          { name: "address", label: "Address", defaultValue: datasetAddress, placeholder: "Optional" },
        ],
        onSubmit(formData) {
          const code = (formData.get("code") || "").trim();
          if (!code) {
            alert("Enter the current code to continue.");
            return false;
          }
          submitAction(
            actionUrl,
            {
              code,
              assigned_to: (formData.get("assigned_to") || "").trim(),
              location: (formData.get("location") || "").trim(),
              address: (formData.get("address") || "").trim(),
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
      return;
    }

    if (itemType === "key") {
      openModal({
        title: `Check Out ${label}`,
        submitLabel: "Check Out",
        fields: [
          {
            name: "copies",
            label: "Number of Copies",
            type: "number",
            required: true,
            defaultValue: "1",
            min: 1,
            help: `${available} copies available`,
          },
          { name: "checked_out_to", label: "Checked Out To", required: true, placeholder: "Name or company" },
          { name: "purpose", label: "Purpose", placeholder: "Optional" },
          { name: "expected_return_date", label: "Expected Return Date", type: "date", placeholder: "Optional" },
        ],
        onSubmit(formData) {
          const copies = parseInt(formData.get("copies"), 10) || 0;
          if (copies < 1 || (available && copies > available)) {
            alert(`Enter a valid number of copies (1-${available || "∞"})`);
            return false;
          }
          submitAction(
            actionUrl,
            {
              copies,
              checked_out_to: (formData.get("checked_out_to") || "").trim(),
              purpose: (formData.get("purpose") || "").trim(),
              expected_return_date: (formData.get("expected_return_date") || "").trim(),
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
      return;
    }

    if (itemType === "sign") {
      openModal({
        title: `Check Out ${label}`,
        submitLabel: "Check Out",
        fields: [
          { name: "purpose", label: "Purpose", placeholder: "e.g., Open House, Listing" },
          { name: "assigned_to", label: "Assigned To", placeholder: "Agent or property name" },
          { name: "address", label: "Property Address", defaultValue: datasetAddress },
          { name: "location", label: "Current Location", defaultValue: datasetLocation },
        ],
        onSubmit(formData) {
          submitAction(
            actionUrl,
            {
              purpose: (formData.get("purpose") || "").trim(),
              assigned_to: (formData.get("assigned_to") || "").trim(),
              address: (formData.get("address") || "").trim(),
              location: (formData.get("location") || "").trim(),
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
    }
  }

  function handleCheckin(button) {
    const actionUrl = button.dataset.action;
    if (!actionUrl || actionUrl === "#") {
      return;
    }
    const label = button.dataset.label || "item";
    const redirectUrl = button.dataset.redirect;
    const redirectAnchor = button.dataset.redirectAnchor;
    const datasetLocation = button.dataset.location || "";
    const datasetAddress = button.dataset.address || "";

    if (itemType === "lockbox") {
      openModal({
        title: `Check In ${label}`,
        submitLabel: "Check In",
        fields: [
          { name: "code", label: "Confirm Code", required: true },
          { name: "location", label: "Location", defaultValue: datasetLocation, placeholder: "Optional" },
          { name: "address", label: "Address", defaultValue: datasetAddress, placeholder: "Optional" },
        ],
        onSubmit(formData) {
          const code = (formData.get("code") || "").trim();
          if (!code) {
            alert("Enter the current code to continue.");
            return false;
          }
          submitAction(
            actionUrl,
            {
              code,
              location: (formData.get("location") || "").trim(),
              address: (formData.get("address") || "").trim(),
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
      return;
    }

    if (itemType === "key" && activeCheckoutsUrl) {
      fetch(activeCheckoutsUrl, { headers: { Accept: "application/json" } })
        .then((response) => {
          if (!response.ok) {
            throw new Error(`Server responded with ${response.status}`);
          }
          return response.json();
        })
        .then((data) => {
          if (!data.checkouts || !data.checkouts.length) {
            alert("No active checkouts found for this key.");
            return;
          }
          const options = [["", "-- Select Checkout --"]].concat(
            data.checkouts.map((checkout) => {
              const base = `${checkout.checked_out_to} (${checkout.quantity})`;
              const when = checkout.checked_out_at ? ` • ${checkout.checked_out_at}` : "";
              return [checkout.id, `${base}${when}`];
            })
          );
          openModal({
            title: `Check In ${label}`,
            submitLabel: "Check In",
            fields: [
              {
                name: "checkout_id",
                label: "Select Checkout to Return",
                widget: "select",
                required: true,
                options,
                help: "Choose which checkout you are returning",
              },
            ],
            onSubmit(formData) {
              const checkoutId = formData.get("checkout_id");
              if (!checkoutId) {
                alert("Select the checkout being returned.");
                return false;
              }
              submitAction(actionUrl, { checkout_id: checkoutId }, redirectUrl, redirectAnchor);
            },
          });
        })
        .catch((error) => {
          console.error("Failed to load checkouts", error);
          alert("Unable to load active checkout information. Please try again.");
        });
      return;
    }

    if (itemType === "sign") {
      openModal({
        title: `Check In ${label}`,
        submitLabel: "Check In",
        fields: [
          { name: "address", label: "Property Address", placeholder: "Where was it placed?" },
          { name: "location", label: "Return Location", placeholder: "Where is it now?" },
        ],
        onSubmit(formData) {
          submitAction(
            actionUrl,
            {
              address: (formData.get("address") || "").trim(),
              location: (formData.get("location") || "").trim(),
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
    }
  }

  function handleAssign(button) {
    const actionUrl = button.dataset.action;
    if (!actionUrl || actionUrl === "#") {
      return;
    }
    const label = button.dataset.label || "item";
    const redirectUrl = button.dataset.redirect;
    const redirectAnchor = button.dataset.redirectAnchor;
    const defaultPropertyId = button.dataset.propertyId || "";
    const defaultUnitId = button.dataset.propertyUnitId || "";
    const available = parseInt(button.dataset.available || availableCopies, 10) || 0;

    if (itemType === "lockbox") {
      openModal({
        title: `Assign ${label}`,
        submitLabel: "Assign",
        fields: [
          { name: "assignee", label: "Assigned To", placeholder: "Name or company (optional when assigning to property)" },
          { name: "assignment_type", label: "Assignment Type", widget: "select", required: true, options: ["agent", "property", "contractor"] },
          { name: "expected_return_date", label: "Expected Return Date", type: "date", placeholder: "Required for contractors" },
          { name: "property_id", label: "Property", widget: "select", options: propertyOptions, defaultValue: defaultPropertyId },
          { name: "address", label: "Property Address", placeholder: "Optional" },
          { name: "location", label: "Location", placeholder: "Optional" },
        ],
        onSubmit(formData) {
          const assignmentType = formData.get("assignment_type");
          const expectedReturn = (formData.get("expected_return_date") || "").trim();
          const propertyId = (formData.get("property_id") || "").trim();
          let assigneeValue = (formData.get("assignee") || "").trim();
          let addressValue = (formData.get("address") || "").trim();
          const locationValue = (formData.get("location") || "").trim();

          if (assignmentType === "contractor" && !expectedReturn) {
            alert("Expected return date is required for contractor assignments.");
            return false;
          }

          if (assignmentType === "property") {
            if (!propertyId) {
              alert("Select a property for this assignment.");
              return false;
            }
            const propertyInfo = propertyMap[propertyId] || null;
            if (!assigneeValue && propertyInfo) {
              assigneeValue = propertyInfo.name || propertyInfo.display || "";
            }
            if (!addressValue && propertyInfo) {
              const addressParts = [
                propertyInfo.address?.line1,
                propertyInfo.address?.city,
                propertyInfo.address?.state,
                propertyInfo.address?.postal_code,
              ];
              addressValue = addressParts.filter(Boolean).join(", ");
            }
          } else if (!assigneeValue) {
            alert("Specify who the lockbox is assigned to.");
            return false;
          }

          submitAction(
            actionUrl,
            {
              assignee: assigneeValue,
              assignment_type: assignmentType,
              expected_return_date: expectedReturn,
              property_id: propertyId,
              address: addressValue,
              location: locationValue,
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
      return;
    }

    if (itemType === "key") {
      openModal({
        title: `Assign ${label}`,
        submitLabel: "Assign",
        fields: [
          {
            name: "copies",
            label: "Number of Copies",
            type: "number",
            required: true,
            defaultValue: "1",
            min: 1,
            help: `${available} copies available`,
          },
          { name: "assigned_to", label: "Assigned To", placeholder: "Name or company (optional if assigning to property)" },
          { name: "assignment_type", label: "Assignment Type", widget: "select", required: true, options: ["tenant", "contractor", "property"] },
          { name: "expected_return_date", label: "Expected Return Date (Contractors)", type: "date", placeholder: "Required for contractors" },
          { name: "property_id", label: "Property", widget: "select", options: propertyOptions, defaultValue: defaultPropertyId, help: "Required when assignment type is Property" },
          { name: "property_unit_id", label: "Property Unit", widget: "select", options: getUnitOptions(defaultPropertyId), defaultValue: defaultUnitId },
        ],
        onSubmit(formData) {
          const copies = parseInt(formData.get("copies"), 10) || 0;
          const assignmentType = formData.get("assignment_type");
          const expectedReturn = (formData.get("expected_return_date") || "").trim();
          const propertyId = (formData.get("property_id") || "").trim();
          const propertyUnitId = (formData.get("property_unit_id") || "").trim();
          let assignedTo = (formData.get("assigned_to") || "").trim();

          if (copies < 1 || (available && copies > available)) {
            alert(`Enter a valid number of copies (1-${available || "∞"})`);
            return false;
          }

          if (assignmentType === "contractor" && !expectedReturn) {
            alert("Expected return date is required for contractor assignments.");
            return false;
          }

          if (assignmentType === "property") {
            if (!propertyId && !propertyUnitId) {
              alert("Select a property or unit for this assignment.");
              return false;
            }
            const propertyInfo = propertyMap[propertyId] || null;
            if (!assignedTo && propertyInfo) {
              assignedTo = propertyInfo.name || propertyInfo.display || "";
              if (propertyUnitId) {
                const unit = (propertyUnits[propertyId] || []).find((u) => u.id === propertyUnitId);
                if (unit) {
                  assignedTo = `${assignedTo} (${unit.label})`;
                }
              }
            }
          } else if (!assignedTo) {
            alert("Please specify who you are assigning the key to.");
            return false;
          }

          submitAction(
            actionUrl,
            {
              copies,
              assignment_type: assignmentType,
              expected_return_date: expectedReturn,
              assigned_to: assignedTo,
              property_id: propertyId,
              property_unit_id: propertyUnitId,
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
      return;
    }

    if (itemType === "sign") {
      openModal({
        title: `Assign ${label}`,
        submitLabel: "Assign",
        fields: [
          { name: "assigned_to", label: "Assigned To", required: true, placeholder: "Agent or company name" },
          { name: "assignment_type", label: "Assignment Type", widget: "select", options: ["agent", "property", "contractor"] },
          { name: "expected_return_date", label: "Expected Return Date", type: "date", placeholder: "Optional" },
          { name: "address", label: "Property Address", placeholder: "Optional" },
          { name: "location", label: "Current Location", placeholder: "Optional" },
        ],
        onSubmit(formData) {
          submitAction(
            actionUrl,
            {
              assigned_to: (formData.get("assigned_to") || "").trim(),
              assignment_type: (formData.get("assignment_type") || "").trim(),
              expected_return_date: (formData.get("expected_return_date") || "").trim(),
              address: (formData.get("address") || "").trim(),
              location: (formData.get("location") || "").trim(),
            },
            redirectUrl,
            redirectAnchor
          );
        },
      });
    }
  }

  function handleAdjustQuantity(button) {
    const actionUrl = button.dataset.action;
    if (!actionUrl || actionUrl === "#") {
      return;
    }
    const label = button.dataset.label || "key";
    const redirectUrl = button.dataset.redirect;
    const redirectAnchor = button.dataset.redirectAnchor;
    const currentTotal = parseInt(button.dataset.total, 10) || 0;

    openModal({
      title: `Adjust Quantity for ${label}`,
      submitLabel: "Update Quantity",
      fields: [
        {
          name: "new_total",
          label: "New Total Copies",
          type: "number",
          required: true,
          defaultValue: String(currentTotal),
          min: 0,
          help: `Currently ${currentTotal} copies recorded`,
        },
        {
          name: "reason",
          label: "Reason",
          widget: "select",
          required: true,
          options: [
            ["made_copy", "Made copy"],
            ["destroyed", "Destroyed"],
            ["lost", "Lost"],
            ["other", "Other"],
          ],
        },
        { name: "notes", label: "Notes", type: "textarea", placeholder: "Optional details" },
      ],
      onSubmit(formData) {
        const newTotal = parseInt(formData.get("new_total"), 10);
        if (Number.isNaN(newTotal) || newTotal < 0) {
          alert("Enter a non-negative number for total copies.");
          return false;
        }
        submitAction(
          actionUrl,
          {
            new_total: newTotal,
            reason: (formData.get("reason") || "").trim(),
            notes: (formData.get("notes") || "").trim(),
          },
          redirectUrl,
          redirectAnchor
        );
      },
    });
  }

  function handleEdit(button) {
    const actionUrl = button.dataset.action;
    if (!actionUrl || actionUrl === "#") {
      return;
    }
    const label = button.dataset.label || "item";
    const redirectUrl = button.dataset.redirect;
    const redirectAnchor = button.dataset.redirectAnchor;

    if (itemType === "lockbox") {
      openModal({
        title: `Edit ${label}`,
        submitLabel: "Save Changes",
        fields: [
          { name: "label", label: "Label", required: true, defaultValue: button.dataset.label || "" },
          { name: "location", label: "Location", defaultValue: button.dataset.location || "", placeholder: "Optional" },
          { name: "address", label: "Address", defaultValue: button.dataset.address || "", placeholder: "Optional" },
          { name: "property_id", label: "Property", widget: "select", options: propertyOptions, defaultValue: button.dataset.propertyId || "" },
          { name: "code_current", label: "Current Code", defaultValue: button.dataset.codeCurrent || "" },
          { name: "code_previous", label: "Previous Code", defaultValue: button.dataset.codePrevious || "" },
          {
            name: "status",
            label: "Status",
            widget: "select",
            options: resolvedStatusOptions.map((value) => [value, friendlyLabel(value)]),
            defaultValue: (button.dataset.status || "").toLowerCase(),
          },
          { name: "assigned_to", label: "Assigned To", defaultValue: button.dataset.assignedTo || "", placeholder: "Optional" },
        ],
        onSubmit(formData) {
          const payload = {
            label: (formData.get("label") || "").trim(),
            location: (formData.get("location") || "").trim(),
            address: (formData.get("address") || "").trim(),
            property_id: (formData.get("property_id") || "").trim(),
            code_current: (formData.get("code_current") || "").trim(),
            code_previous: (formData.get("code_previous") || "").trim(),
            status: (formData.get("status") || "").trim(),
            assigned_to: (formData.get("assigned_to") || "").trim(),
          };
          if (!payload.label) {
            alert("Label is required.");
            return false;
          }
          submitAction(actionUrl, payload, redirectUrl, redirectAnchor);
        },
      });
      return;
    }

    if (itemType === "key") {
      const defaultPropertyId = button.dataset.propertyId || "";
      const defaultUnitId = button.dataset.propertyUnitId || "";
      openModal({
        title: `Edit ${label}`,
        submitLabel: "Save Changes",
        fields: [
          { name: "label", label: "Label", required: true, defaultValue: button.dataset.label || "" },
          { name: "location", label: "Key Box Location", defaultValue: button.dataset.location || "" },
          { name: "address", label: "Address", defaultValue: button.dataset.address || "" },
          { name: "key_hook_number", label: "Key Hook #", defaultValue: button.dataset.keyHook || "" },
          { name: "keycode", label: "Key Code", defaultValue: button.dataset.keycode || "" },
          { name: "total_copies", label: "Total Copies", type: "number", defaultValue: button.dataset.total || "0", min: 0 },
          {
            name: "status",
            label: "Status",
            widget: "select",
            options: resolvedStatusOptions.map((value) => [value, friendlyLabel(value)]),
            defaultValue: (button.dataset.status || "").toLowerCase(),
          },
          { name: "property_id", label: "Property", widget: "select", options: propertyOptions, defaultValue: defaultPropertyId },
          { name: "property_unit_id", label: "Property Unit", widget: "select", options: getUnitOptions(defaultPropertyId), defaultValue: defaultUnitId },
          { name: "assigned_to", label: "Assigned To", defaultValue: button.dataset.assignedTo || "" },
        ],
        onSubmit(formData) {
          const payload = {
            label: (formData.get("label") || "").trim(),
            location: (formData.get("location") || "").trim(),
            address: (formData.get("address") || "").trim(),
            key_hook_number: (formData.get("key_hook_number") || "").trim(),
            keycode: (formData.get("keycode") || "").trim(),
            total_copies: parseInt(formData.get("total_copies"), 10) || 0,
            status: (formData.get("status") || "").trim(),
            assigned_to: (formData.get("assigned_to") || "").trim(),
            property_id: (formData.get("property_id") || "").trim(),
            property_unit_id: (formData.get("property_unit_id") || "").trim(),
          };
          if (!payload.label) {
            alert("Label is required.");
            return false;
          }
          submitAction(actionUrl, payload, redirectUrl, redirectAnchor);
        },
      });
      return;
    }

    if (itemType === "sign") {
      openModal({
        title: `Edit ${label}`,
        submitLabel: "Save Changes",
        fields: [
          { name: "label", label: "Label", required: true, defaultValue: button.dataset.label || "" },
          { name: "sign_subtype", label: "Sign Type", defaultValue: button.dataset.signSubtype || "" },
          {
            name: "piece_type",
            label: "Piece Type",
            widget: "select",
            options: [["", "-- None --"]].concat(pieceTypes.map((value) => [value, friendlyLabel(value)])),
            defaultValue: button.dataset.pieceType || "",
          },
          { name: "rider_text", label: "Rider Text", defaultValue: button.dataset.riderText || "" },
          { name: "material", label: "Material", defaultValue: button.dataset.material || "" },
          {
            name: "condition",
            label: "Condition",
            widget: "select",
            options: [["", "-- None --"]].concat((conditionOptions || []).map((value) => [value, friendlyLabel(value)])),
            defaultValue: button.dataset.condition || "",
          },
          { name: "location", label: "Storage Location", defaultValue: button.dataset.location || "" },
          { name: "address", label: "Property Address", defaultValue: button.dataset.address || "" },
          {
            name: "status",
            label: "Status",
            widget: "select",
            options: resolvedStatusOptions.map((value) => [value, friendlyLabel(value)]),
            defaultValue: (button.dataset.status || "").toLowerCase(),
          },
          { name: "assigned_to", label: "Assigned To", defaultValue: button.dataset.assignedTo || "" },
        ],
        onSubmit(formData) {
          const payload = {
            label: (formData.get("label") || "").trim(),
            sign_subtype: (formData.get("sign_subtype") || "").trim(),
            piece_type: (formData.get("piece_type") || "").trim(),
            rider_text: (formData.get("rider_text") || "").trim(),
            material: (formData.get("material") || "").trim(),
            condition: (formData.get("condition") || "").trim(),
            location: (formData.get("location") || "").trim(),
            address: (formData.get("address") || "").trim(),
            status: (formData.get("status") || "").trim(),
            assigned_to: (formData.get("assigned_to") || "").trim(),
          };
          if (!payload.label) {
            alert("Label is required.");
            return false;
          }
          submitAction(actionUrl, payload, redirectUrl, redirectAnchor);
        },
      });
    }
  }

  Array.from(document.querySelectorAll(".js-checkout-action")).forEach((button) => {
    button.addEventListener("click", () => handleCheckout(button));
  });

  Array.from(document.querySelectorAll(".js-checkin-action")).forEach((button) => {
    button.addEventListener("click", () => handleCheckin(button));
  });

  Array.from(document.querySelectorAll(".js-assign-action")).forEach((button) => {
    button.addEventListener("click", () => handleAssign(button));
  });

  if (itemType === "key") {
    Array.from(document.querySelectorAll(".js-adjust-qty-action")).forEach((button) => {
      button.addEventListener("click", () => handleAdjustQuantity(button));
    });
  }

  Array.from(document.querySelectorAll(".js-edit-action")).forEach((button) => {
    button.addEventListener("click", () => handleEdit(button));
  });

  try {
    delete window.kbmItemDetails;
  } catch (error) {
    window.kbmItemDetails = undefined;
  }
})();
