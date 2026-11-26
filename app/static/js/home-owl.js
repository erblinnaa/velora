(() => {
  const vz = document.getElementById('vz');
  const stage = document.getElementById('stage');
  const owl = document.getElementById('owl');
  const pupils = [document.getElementById('pL'), document.getElementById('pR')];
  const toggle = document.getElementById('tm');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const storageKey = 'velora-theme';

  /* Tema: e njëjta zgjedhje si në pjesën tjetër të aplikacionit */
  function showTheme(theme) {
    document.documentElement.dataset.theme = theme;
    vz.classList.toggle('night', theme === 'dark');
    toggle.textContent = theme === 'dark' ? 'ditë' : 'natë';
  }

  toggle.addEventListener('click', () => {
    const theme = vz.classList.contains('night') ? 'light' : 'dark';
    showTheme(theme);
    try {
      localStorage.setItem(storageKey, theme);
    } catch (error) {
      // Tema ndryshon edhe kur shfletuesi nuk lejon ruajtjen.
    }
  });
  showTheme(document.documentElement.dataset.theme);
  toggle.hidden = false;

  document.querySelectorAll('[data-dismiss]').forEach((button) => {
    button.addEventListener('click', () => button.closest('.msg').remove());
  });

  /* Bufi: sytë ndjekin kursorin dhe pulisin */
  function look(x, y) {
    pupils.forEach((pupil) => {
      pupil.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`;
    });
  }

  stage.addEventListener('pointermove', (event) => {
    const box = owl.getBoundingClientRect();
    const scale = box.width / 190;
    const dx = event.clientX - (box.left + 95 * scale);
    const dy = event.clientY - (box.top + 84 * scale);
    const distance = Math.hypot(dx, dy) || 1;
    const reach = Math.min(8, distance / 22);
    look((dx / distance) * reach, (dy / distance) * reach);
  });
  stage.addEventListener('pointerleave', () => look(0, 0));

  function blink() {
    if (!reducedMotion.matches) {
      owl.classList.add('blink');
      setTimeout(() => owl.classList.remove('blink'), 140);
    }
    setTimeout(blink, 2600 + Math.random() * 3000);
  }
  setTimeout(blink, 1500);
})();
