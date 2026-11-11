document.addEventListener("DOMContentLoaded", () => {
  // ---- mobile menu ----
  const toggle = document.querySelector(".menu-toggle");
  const nav = document.querySelector(".nav-links");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }

  // ---- close flash messages ----
  document.querySelectorAll(".flash-close").forEach(button => {
    button.addEventListener("click", () => button.closest(".flash")?.remove());
  });

  // ---- form validation + confirm dialogs ----
  document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", event => {
      if (!form.checkValidity()) {
        event.preventDefault();
        form.reportValidity();
        return;
      }
      const message = form.dataset.confirm;
      if (message && !window.confirm(message)) {
        event.preventDefault();
        return;
      }
      // forms handled by their own script (e.g. the "Show route" box) keep their button enabled
      if (form.hasAttribute("data-no-lock")) return;
      // stop double-clicks on submit buttons
      form.querySelectorAll("button[type=submit], button:not([type])").forEach(b => {
        setTimeout(() => { b.disabled = true; }, 0);
      });
    });
  });

  // ---- show / hide password (the eye button) ----
  document.querySelectorAll("[data-toggle-password]").forEach(button => {
    button.addEventListener("click", () => {
      const input = button.closest(".pw-wrap").querySelector("input");
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      button.setAttribute("aria-pressed", String(show));
      button.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });
  });

  // ---- payment method: show the right instructions, hide reference for cash ----
  const methods = document.querySelectorAll("[data-pay-method]");
  if (methods.length) {
    const refBox = document.querySelector("[data-pay-ref]");
    const refInput = refBox ? refBox.querySelector("input") : null;
    const update = () => {
      const chosen = document.querySelector("[data-pay-method]:checked")?.value;
      document.querySelectorAll("[data-pay-help]").forEach(el => { el.hidden = el.dataset.payHelp !== chosen; });
      if (refBox) {
        const needRef = chosen !== "cash_onsite";
        refBox.hidden = !needRef;
        if (refInput) { refInput.required = needRef; if (!needRef) refInput.value = ""; }
      }
    };
    methods.forEach(m => m.addEventListener("change", update));
    update();
  }

  // ---- product photo preview (optional photo; default picture follows the category) ----
  const imageInput = document.getElementById("image-input");
  const preview = document.getElementById("image-preview");
  const category = document.getElementById("category-select");
  if (preview) {
    const defaults = JSON.parse(preview.dataset.defaults || "{}");
    let hasPhoto = preview.dataset.hasPhoto === "1";
    const showDefault = () => {
      if (!hasPhoto) preview.src = defaults[category.value] || preview.src;
    };
    if (category) category.addEventListener("change", showDefault);
    if (imageInput) {
      imageInput.addEventListener("change", () => {
        const file = imageInput.files[0];
        if (file) {
          preview.src = URL.createObjectURL(file);
          hasPhoto = true;
        } else {
          hasPhoto = preview.dataset.hasPhoto === "1";
          showDefault();
        }
      });
    }
    if (!hasPhoto && category) showDefault();
  }
});
