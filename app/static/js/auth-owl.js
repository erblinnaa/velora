(() => {
  const vz = document.getElementById('vz');
  const stage = document.getElementById('stage');
  const owl = document.getElementById('owl');
  const form = document.getElementById('card');
  const pupils = [document.getElementById('pL'), document.getElementById('pR')];
  const go = form.querySelector('.go');
  const goText = go.querySelector('.gt');
  const idleText = goText.textContent;
  const fields = [...form.querySelectorAll('input[data-rule]')];
  const eyes = [...form.querySelectorAll('.eb')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const ctx = document.createElement('canvas').getContext('2d');
  const EYE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  const EYE_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 4.4-1"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>';
  let busy = false;
  let submitTimer;

  // Mesazhet shqipe i shfaq vetë formulari; pa JavaScript mbeten ato të shfletuesit.
  form.noValidate = true;

  // Llogaria e re merr temën që shihet në ekran.
  form.querySelectorAll('[data-theme-field]').forEach((field) => {
    field.value = vz.classList.contains('night') ? 'dark' : 'light';
  });

  function isValid(field) {
    const value = field.value;
    if (field.dataset.rule === 'email') return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value.trim());
    if (field.dataset.rule === 'name') {
      const length = value.trim().length;
      return length >= 2 && length <= 120;
    }
    return value.length >= Number(field.dataset.min);
  }

  function mark(field, bad) {
    const hint = document.getElementById(`${field.id}-hint`);
    field.classList.toggle('bad', bad);
    hint.classList.toggle('on', bad);
    if (bad) {
      field.setAttribute('aria-invalid', 'true');
      field.setAttribute('aria-describedby', hint.id);
    } else {
      field.removeAttribute('aria-invalid');
      field.removeAttribute('aria-describedby');
    }
  }

  function showCheck(field) {
    field.parentElement.querySelector('.ok')?.classList.toggle('on', isValid(field));
  }

  function look(x, y) {
    pupils.forEach((pupil) => {
      pupil.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`;
    });
  }

  function followText(field) {
    ctx.font = getComputedStyle(field).font;
    const width = ctx.measureText(field.value).width;
    const ratio = Math.max(0, Math.min(1, width / (field.clientWidth - 56)));
    look(-8 + 16 * ratio, 7);
  }

  function cover(peek) {
    owl.classList.add('cover');
    owl.classList.toggle('peek', peek);
  }

  function uncover() {
    owl.classList.remove('cover', 'peek');
  }

  function play(name, ms) {
    owl.classList.remove('happy', 'worry');
    void owl.getBoundingClientRect();
    owl.classList.add(name);
    setTimeout(() => owl.classList.remove(name), ms);
  }

  stage.addEventListener('pointermove', (event) => {
    if (busy || fields.includes(document.activeElement)) return;
    const box = owl.getBoundingClientRect();
    const scale = box.width / 190;
    const dx = event.clientX - (box.left + 95 * scale);
    const dy = event.clientY - (box.top + 84 * scale);
    const distance = Math.hypot(dx, dy) || 1;
    const reach = Math.min(8, distance / 22);
    look((dx / distance) * reach, (dy / distance) * reach);
  });
  stage.addEventListener('pointerleave', () => {
    if (!fields.includes(document.activeElement)) look(0, 0);
  });

  // Sytë mbeten të mbuluar sa kohë fokusi është te një fjalëkalim ose te butoni i syrit.
  function uncoverLater() {
    setTimeout(() => {
      const active = document.activeElement;
      const secret = eyes.includes(active) || (fields.includes(active) && active.dataset.rule === 'password');
      if (!secret) uncover();
    }, 60);
  }

  fields.forEach((field) => {
    if (field.dataset.rule === 'password') {
      const eye = field.parentElement.querySelector('.eb');
      const onFocus = () => cover(field.type === 'text');
      field.addEventListener('focus', onFocus);
      field.addEventListener('input', () => {
        if (isValid(field)) mark(field, false);
      });
      field.addEventListener('blur', uncoverLater);

      eye.hidden = false;
      eye.addEventListener('blur', uncoverLater);
      eye.addEventListener('mousedown', (event) => event.preventDefault());
      eye.addEventListener('click', () => {
        const show = field.type === 'password';
        field.type = show ? 'text' : 'password';
        eye.innerHTML = show ? EYE_OFF : EYE;
        eye.setAttribute('aria-label', show ? 'Fshih fjalëkalimin' : 'Shfaq fjalëkalimin');
        field.focus();
        cover(show);
      });
      if (document.activeElement === field) onFocus();
      return;
    }

    const onFocus = () => {
      uncover();
      followText(field);
    };
    field.addEventListener('focus', onFocus);
    field.addEventListener('input', () => {
      followText(field);
      showCheck(field);
      if (isValid(field)) mark(field, false);
    });
    field.addEventListener('blur', () => {
      look(0, 0);
      if (field.value && !isValid(field)) mark(field, true);
    });
    showCheck(field);
    if (document.activeElement === field) onFocus();
  });

  form.addEventListener('submit', (event) => {
    if (busy) {
      event.preventDefault();
      return;
    }
    let allValid = true;
    fields.forEach((field) => {
      const valid = isValid(field);
      mark(field, !valid);
      if (!valid) allValid = false;
    });
    uncover();
    if (!allValid) {
      event.preventDefault();
      look(0, 5);
      play('worry', 900);
      return;
    }
    busy = true;
    look(0, 0);
    play('happy', 1800);
    go.classList.add('load');
    go.setAttribute('aria-busy', 'true');
    goText.textContent = form.dataset.loading;
    // Bufi gëzohet pak para dërgimit; me lëvizje të reduktuar dërgohet menjëherë.
    if (!reducedMotion.matches) {
      event.preventDefault();
      submitTimer = setTimeout(() => form.submit(), 600);
    }
  });

  // Kur kthehesh me butonin "mbrapa", formulari duhet të punojë përsëri.
  window.addEventListener('pageshow', (event) => {
    if (!event.persisted) return;
    clearTimeout(submitTimer);
    busy = false;
    go.classList.remove('load');
    go.removeAttribute('aria-busy');
    goText.textContent = idleText;
  });

  function blink() {
    if (!reducedMotion.matches && !owl.classList.contains('cover') && !owl.classList.contains('happy')) {
      owl.classList.add('blink');
      setTimeout(() => owl.classList.remove('blink'), 140);
    }
    setTimeout(blink, 2600 + Math.random() * 3000);
  }
  setTimeout(blink, 1500);

  if (form.querySelector('[data-worry]')) play('worry', 900);
})();
