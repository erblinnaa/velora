(() => {
  const root = document.documentElement;
  const body = document.body;
  const storageKey = 'velora-theme';

  /* Tema */
  const themeButtons = document.querySelectorAll('[data-set-theme]');

  function showTheme(theme) {
    root.dataset.theme = theme;
    themeButtons.forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.setTheme === theme));
    });
    document.querySelectorAll('input[type="radio"][name="theme"]').forEach((radio) => {
      radio.checked = radio.value === theme;
    });
  }

  function saveTheme(theme) {
    try {
      localStorage.setItem(storageKey, theme);
    } catch (error) {
      // Tema ndryshon edhe kur shfletuesi nuk lejon ruajtjen.
    }

    // Për përdoruesit e kyçur tema ruhet edhe në llogari.
    if (body.dataset.themeUrl) {
      fetch(body.dataset.themeUrl, {
        method: 'POST',
        headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': body.dataset.csrf },
        body: new URLSearchParams({ theme }),
        keepalive: true,
      }).catch(() => {});
    }
  }

  themeButtons.forEach((button) => {
    button.addEventListener('click', () => {
      showTheme(button.dataset.setTheme);
      saveTheme(button.dataset.setTheme);
    });
  });
  showTheme(root.dataset.theme);

  /* Fleta "+" në telefon */
  const sheet = document.getElementById('add-sheet');
  const sheetButton = document.querySelector('[data-sheet-open]');
  if (sheet?.showModal && sheetButton) {
    sheetButton.setAttribute('role', 'button');
    sheetButton.setAttribute('aria-haspopup', 'dialog');
    sheetButton.addEventListener('click', (event) => {
      event.preventDefault();
      sheet.showModal();
    });
    sheet.addEventListener('click', (event) => {
      // Mbyllet nga butoni, nga një lidhje ose nga prekja jashtë fletës.
      const outside = event.target === sheet && event.clientY < sheet.getBoundingClientRect().top;
      if (outside || event.target.closest('a, [data-sheet-close]')) sheet.close();
    });
    window.matchMedia('(min-width: 900px)').addEventListener('change', (query) => {
      if (query.matches && sheet.open) sheet.close();
    });
  }

  /* Lista e lëndëve te "Shto material" mbyllet me Escape ose me klikim jashtë */
  const headerPicker = document.querySelector('.picker-header');
  document.addEventListener('click', (event) => {
    if (headerPicker && !headerPicker.contains(event.target)) headerPicker.open = false;
  });
  headerPicker?.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !headerPicker.open) return;
    headerPicker.open = false;
    headerPicker.querySelector('summary').focus();
  });

  /* Lidhjet si #shto-material hapin seksionin përkatës */
  function openTarget() {
    const target = document.getElementById(window.location.hash.slice(1));
    if (target?.tagName === 'DETAILS') target.open = true;
  }
  window.addEventListener('hashchange', openTarget);
  // Edhe kur adresa e ka tashmë atë #, prandaj nuk ndodh "hashchange".
  document.addEventListener('click', (event) => {
    if (event.target.closest('a[href*="#"]')) setTimeout(openTarget);
  });
  openTarget();

  /* Mesazhet dhe butoni "Kthehu mbrapa" */
  document.querySelectorAll('[data-dismiss]').forEach((button) => {
    button.addEventListener('click', () => button.closest('.flash').remove());
  });
  // "Anulo" hiqet kur kalon afati i serverit.
  document.querySelectorAll('[data-expires]').forEach((message) => {
    setTimeout(() => message.remove(), Number(message.dataset.expires) * 1000);
  });
  document.querySelector('[data-back]')?.addEventListener('click', () => window.history.back());

  /* Formularët: konfirmimi, gjendja e pritjes dhe bllokimi i dërgimit të dyfishtë */
  let busy = [];

  function startLoading(button) {
    busy.push({ button, content: button.innerHTML });
    const spinner = document.createElement('span');
    spinner.className = 'spinner';
    spinner.setAttribute('aria-hidden', 'true');
    button.replaceChildren(spinner, button.dataset.loading);
    button.setAttribute('aria-busy', 'true');
  }

  function resetForms() {
    busy.forEach(({ button, content }) => {
      button.innerHTML = content;
      button.removeAttribute('aria-busy');
    });
    busy = [];
    document.querySelectorAll('button[data-locked]').forEach((button) => {
      button.disabled = false;
      delete button.dataset.locked;
    });
    document.querySelectorAll('form[data-submitting]').forEach((form) => {
      delete form.dataset.submitting;
    });
    document.querySelectorAll('.ai-status').forEach((status) => status.remove());
  }

  function lock(button) {
    if (button.disabled) return;
    button.disabled = true;
    button.dataset.locked = 'true';
  }

  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', (event) => {
      if (form.dataset.submitting) {
        event.preventDefault();
        return;
      }
      if (form.dataset.confirm && !window.confirm(form.dataset.confirm)) {
        event.preventDefault();
        return;
      }
      form.dataset.submitting = 'true';

      const button = form.querySelector('button[type="submit"]');
      if (!button) return;
      // Format me AI e tregojnë pritjen poshtë butonit.
      if (button.dataset.loading && !form.hasAttribute('data-ai')) startLoading(button);
      lock(button);

      // Vetëm një kërkesë AI në të njëjtën kohë.
      if (form.hasAttribute('data-ai')) {
        document.querySelectorAll('form[data-ai] button[type="submit"]').forEach(lock);
        const status = document.createElement('p');
        status.className = 'ai-status';
        status.setAttribute('role', 'status');
        const spinner = document.createElement('span');
        spinner.className = 'spinner';
        spinner.setAttribute('aria-hidden', 'true');
        status.append(spinner, 'Velora po e përgatit… Mund të zgjasë pak, mos e mbyll faqen.');
        form.parentElement.append(status);
      }
    });
  });

  // Kur kthehesh me butonin "mbrapa", butonat duhet të punojnë përsëri.
  window.addEventListener('pageshow', (event) => {
    if (event.persisted) resetForms();
  });

  /* Mesazhet e validimit të shfletuesit, në shqip */
  function albanianMessage(field) {
    const state = field.validity;
    if (state.valueMissing) {
      if (field.type === 'radio') return 'Zgjidh një alternativë.';
      if (field.tagName === 'SELECT') return 'Zgjidh një nga opsionet.';
      return 'Plotëso këtë fushë.';
    }
    if (state.typeMismatch) return 'Shkruaj një adresë email-i të vlefshme.';
    if (state.tooShort) return `Shkruaj të paktën ${field.minLength} karaktere.`;
    return 'Kontrollo këtë fushë.';
  }

  document.querySelectorAll('input, textarea, select').forEach((field) => {
    if (field.type === 'file') return;
    field.addEventListener('invalid', () => {
      field.setCustomValidity('');
      if (!field.validity.valid) field.setCustomValidity(albanianMessage(field));
    });
    const clear = () => {
      const group = field.type === 'radio' && field.form
        ? field.form.querySelectorAll(`input[name="${field.name}"]`)
        : [field];
      group.forEach((item) => item.setCustomValidity(''));
    };
    field.addEventListener('input', clear);
    field.addEventListener('change', clear);
  });

  /* Zgjedhja e PDF-së */
  document.querySelectorAll('input[type="file"]').forEach((input) => {
    const label = input.closest('.field').querySelector('.file-name');
    input.addEventListener('change', () => {
      const file = input.files[0];
      const limit = Number(input.dataset.maxBytes);
      input.closest('.field').querySelector('.field-error')?.remove();
      input.removeAttribute('aria-invalid');

      if (file && limit && file.size >= limit) {
        const error = document.createElement('p');
        error.className = 'field-error';
        error.setAttribute('role', 'alert');
        error.textContent = `Dokumenti “${file.name}” është më i madh se kufiri i lejuar.`;
        input.closest('.field').append(error);
        input.setAttribute('aria-invalid', 'true');
        input.value = '';
      }
      label.textContent = input.files.length ? input.files[0].name : label.dataset.empty;
    });
  });
})();
