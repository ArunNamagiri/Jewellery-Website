document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.getElementById("navToggle");
  var menu = document.getElementById("mobileNav");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var isOpen = menu.classList.toggle("open");
      toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });
  }

  // Auto-dismiss flash messages after a few seconds
  document.querySelectorAll(".flash").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.4s ease";
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 400);
    }, 4500);
  });

  // Chat widget
  var chatToggle = document.getElementById("chatToggle");
  var chatPanel = document.getElementById("chatPanel");
  var chatClose = document.getElementById("chatClose");
  var chatForm = document.getElementById("chatForm");
  var chatInput = document.getElementById("chatInput");
  var chatMessages = document.getElementById("chatMessages");

  if (chatToggle && chatPanel) {
    chatToggle.addEventListener("click", function () {
      chatPanel.classList.toggle("open");
    });
    chatClose.addEventListener("click", function () {
      chatPanel.classList.remove("open");
    });
    chatForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var text = chatInput.value.trim();
      if (!text) return;
      appendChatMessage(text, "user");
      chatInput.value = "";

      fetch("/chatbot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text })
      })
        .then(function (res) { return res.json(); })
        .then(function (data) { appendChatMessage(data.reply, "bot"); })
        .catch(function () {
          appendChatMessage("Sorry, something went wrong. Please try our Contact page instead.", "bot");
        });
    });
  }

  function appendChatMessage(text, who) {
    var div = document.createElement("div");
    div.className = "chat-msg chat-msg-" + who;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
});
