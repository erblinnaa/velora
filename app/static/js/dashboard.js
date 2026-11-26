/* Përshëndetja sipas orës lokale të përdoruesit. */
(() => {
  const greeting = document.querySelector('[data-greeting]');
  if (!greeting) return;
  const hour = new Date().getHours();
  let word = 'Mirëmbrëma';
  if (hour >= 5 && hour < 12) word = 'Mirëmëngjes';
  else if (hour >= 12 && hour < 18) word = 'Mirëdita';
  greeting.textContent = `${word}, ${greeting.dataset.greeting}.`;
})();
