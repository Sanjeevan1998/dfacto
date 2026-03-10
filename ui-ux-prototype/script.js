document.addEventListener("DOMContentLoaded", () => {
  const listenButton = document.getElementById("listenButton");
  const audioHeader = document.getElementById("audioHeader");
  const audioTitle = document.getElementById("audioTitle");
  const audioSubtitle = document.getElementById("audioSubtitle");
  const audioStatusCard = document.getElementById("audioStatusCard");
  const toggleButtons = document.querySelectorAll(".toggle-btn");

  if (listenButton) {
    listenButton.addEventListener("click", () => {
      if (listenButton.classList.contains("processing")) return;

      listenButton.classList.add("processing");
      listenButton.classList.add("listening");

      if (audioHeader) audioHeader.classList.add("listening");
      if (audioTitle) audioTitle.textContent = "Listening...";
      if (audioSubtitle) {
        audioSubtitle.textContent = "DFacto is capturing and transcribing the audio in real time.";
      }

      if (audioStatusCard) {
        audioStatusCard.innerHTML = `
          <div class="status-row">
            <span class="material-symbols-outlined">graphic_eq</span>
            <div>
              <h4>Listening in progress</h4>
              <p>Live speech is being transcribed and analyzed for factual claims.</p>
            </div>
          </div>
        `;
      }

      setTimeout(() => {
        window.location.href = "factcheck.html";
      }, 2500);
    });
  }

  toggleButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const chipId = button.getAttribute("data-chip");
      const chip = document.getElementById(chipId);

      button.classList.toggle("active-toggle");

      if (button.classList.contains("active-toggle")) {
        button.textContent = "ON";
        if (chip) chip.classList.add("active");
      } else {
        button.textContent = "OFF";
        if (chip) chip.classList.remove("active");
      }
    });
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const nav = document.getElementById("bottomNav");
  const activePill = document.getElementById("navActivePill");
  const navItems = nav?.querySelectorAll(".nav-item");

  if (!nav || !activePill || !navItems?.length) return;

  const activeItem = nav.querySelector(".nav-item.active");
  if (!activeItem) return;

  function movePillTo(target) {
    const navRect = nav.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    const offset = targetRect.left - navRect.left + (targetRect.width - 44) / 2;
    activePill.style.transform = `translateX(${offset}px)`;
  }

  movePillTo(activeItem);

  navItems.forEach((item) => {
    item.addEventListener("click", (e) => {
      movePillTo(item);
    });
  });

  window.addEventListener("resize", () => {
    const currentActive = nav.querySelector(".nav-item.active");
    if (currentActive) movePillTo(currentActive);
  });
});