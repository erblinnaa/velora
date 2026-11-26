(() => {
  const vz = document.getElementById('vz');
  const toggle = document.getElementById('tm');
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
})();
