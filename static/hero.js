(function () {
  const el = document.getElementById("typing-title");
  if (!el) return;

  const text = "Reorder text with syntax-aware intelligence";
  let index = 0;

  function getSpeed(char) {
    if (char === " ") return 20;
    if (char === ".") return 200;
    if (char === ",") return 120;
    return 35 + Math.random() * 30;
  }

  function typeEffect() {
    if (index < text.length) {
      el.textContent += text.charAt(index);
      index += 1;
      setTimeout(typeEffect, getSpeed(text.charAt(index)));
    } else {
      document.body.classList.add("typing-done");
    }
  }

  window.addEventListener("load", typeEffect);
})();
