/* Bufi i faqes kryesore dhe i panelit: sytë ndjekin kursorin dhe pulisin. */
(() => {
  const owl = document.getElementById('owl');
  if (!owl) return;
  const pupils = [document.getElementById('pL'), document.getElementById('pR')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

  function look(x, y) {
    pupils.forEach((pupil) => {
      pupil.style.transform = `translate(${x.toFixed(1)}px,${y.toFixed(1)}px)`;
    });
  }

  document.addEventListener('pointermove', (event) => {
    const box = owl.getBoundingClientRect();
    const scale = box.width / 190;
    const dx = event.clientX - (box.left + 95 * scale);
    const dy = event.clientY - (box.top + 84 * scale);
    const distance = Math.hypot(dx, dy) || 1;
    const reach = Math.min(8, distance / 22);
    look((dx / distance) * reach, (dy / distance) * reach);
  });
  document.documentElement.addEventListener('pointerleave', () => look(0, 0));

  function blink() {
    if (!reducedMotion.matches) {
      owl.classList.add('blink');
      setTimeout(() => owl.classList.remove('blink'), 140);
    }
    setTimeout(blink, 2600 + Math.random() * 3000);
  }
  setTimeout(blink, 1500);
})();
