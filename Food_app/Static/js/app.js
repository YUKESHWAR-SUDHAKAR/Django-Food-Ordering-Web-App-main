document.addEventListener("DOMContentLoaded", function () {
  const root = document.documentElement;
  const themeToggle = document.getElementById("themeToggle");
  const navSearchInput = document.getElementById("navSearchInput");
  const voiceSearchButton = document.getElementById("voiceSearchButton");
  const notificationBadge = document.getElementById("notificationBadge");
  const notificationList = document.getElementById("notificationList");
  const chatToggle = document.getElementById("chatToggle");
  const chatPanel = document.getElementById("chatPanel");
  const chatClose = document.getElementById("chatClose");
  const chatReplyBox = document.getElementById("chatReplyBox");
  const deliverySlotField = document.getElementById("deliverySlotField");
  const scheduledField = document.getElementById("scheduledForWrap");
  const pincodeInput = document.getElementById("deliveryPincode");
  const deliveryStatusBox = document.getElementById("deliveryAvailability");
  const detectLocationButton = document.getElementById("detectLocationButton");
  const latitudeInput = document.getElementById("locationLat");
  const longitudeInput = document.getElementById("locationLng");

  function syncThemeIcon() {
    if (!themeToggle) {
      return;
    }
    const icon = themeToggle.querySelector("i");
    const currentTheme = root.getAttribute("data-theme") || "light";
    icon.className = currentTheme === "dark" ? "fa-solid fa-sun" : "fa-solid fa-moon";
  }

  if (themeToggle) {
    syncThemeIcon();
    themeToggle.addEventListener("click", function () {
      const currentTheme = root.getAttribute("data-theme") || "light";
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", nextTheme);
      localStorage.setItem("theme", nextTheme);
      syncThemeIcon();
    });
  }

  if (voiceSearchButton && navSearchInput) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      voiceSearchButton.disabled = true;
      voiceSearchButton.title = "Voice search is not supported in this browser.";
    } else {
      voiceSearchButton.addEventListener("click", function () {
        const recognition = new SpeechRecognition();
        recognition.lang = "en-IN";
        recognition.start();
        voiceSearchButton.classList.add("is-listening");
        recognition.onresult = function (event) {
          navSearchInput.value = event.results[0][0].transcript;
          navSearchInput.form.submit();
        };
        recognition.onerror = function () {
          voiceSearchButton.classList.remove("is-listening");
        };
        recognition.onend = function () {
          voiceSearchButton.classList.remove("is-listening");
        };
      });
    }
  }

  if (chatToggle && chatPanel) {
    chatToggle.addEventListener("click", function () {
      chatPanel.classList.toggle("d-none");
    });
  }

  if (chatClose && chatPanel) {
    chatClose.addEventListener("click", function () {
      chatPanel.classList.add("d-none");
    });
  }

  document.querySelectorAll("[data-chat-reply]").forEach(function (button) {
    button.addEventListener("click", function () {
      if (chatReplyBox) {
        chatReplyBox.textContent = button.dataset.chatReply;
      }
    });
  });

  document.querySelectorAll("[data-auto-submit]").forEach(function (field) {
    field.addEventListener("change", function () {
      if (field.form) {
        field.form.submit();
      }
    });
  });

  function toggleScheduledField() {
    if (!deliverySlotField || !scheduledField) {
      return;
    }
    scheduledField.classList.toggle("d-none", deliverySlotField.value !== "Later");
  }

  if (deliverySlotField) {
    toggleScheduledField();
    deliverySlotField.addEventListener("change", toggleScheduledField);
  }

  function updateDeliveryAvailability(message, available) {
    if (!deliveryStatusBox) {
      return;
    }
    deliveryStatusBox.textContent = message;
    deliveryStatusBox.className = available ? "availability-banner available" : "availability-banner unavailable";
  }

  if (pincodeInput) {
    pincodeInput.addEventListener("blur", function () {
      const value = pincodeInput.value.trim();
      if (!value) {
        return;
      }
      fetch("/delivery-availability/?pincode=" + encodeURIComponent(value))
        .then(function (response) { return response.json(); })
        .then(function (data) {
          updateDeliveryAvailability(data.message, data.available);
        })
        .catch(function () {
          updateDeliveryAvailability("Unable to check delivery availability right now.", false);
        });
    });
  }

  if (detectLocationButton && latitudeInput && longitudeInput) {
    detectLocationButton.addEventListener("click", function () {
      if (!navigator.geolocation) {
        updateDeliveryAvailability("Location access is not supported in this browser.", false);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        function (position) {
          latitudeInput.value = position.coords.latitude.toFixed(6);
          longitudeInput.value = position.coords.longitude.toFixed(6);
          updateDeliveryAvailability("Location captured successfully for delivery.", true);
        },
        function () {
          updateDeliveryAvailability("Location permission was denied.", false);
        }
      );
    });
  }

  document.querySelectorAll("[data-product-qty]").forEach(function (wrapper) {
    const input = wrapper.querySelector("input");
    wrapper.querySelectorAll("[data-qty-change]").forEach(function (button) {
      button.addEventListener("click", function () {
        const nextValue = (parseInt(input.value, 10) || 1) + (button.dataset.qtyChange === "up" ? 1 : -1);
        input.value = Math.max(1, Math.min(10, nextValue));
      });
    });
  });

  const cartButton = document.getElementById("productCartButton");
  const wishButton = document.getElementById("productWishButton");
  const productIdField = document.getElementById("productIdField");
  const productQtyField = document.getElementById("productQtyField");
  const csrfField = document.querySelector("[name=csrfmiddlewaretoken]");

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "X-CSRFToken": csrfField ? csrfField.value : "",
      },
      body: JSON.stringify(payload),
    }).then(function (response) { return response.json(); });
  }

  if (cartButton && productIdField && productQtyField) {
    cartButton.addEventListener("click", function () {
      postJson("/addtocart/", {
        product_id: productIdField.value,
        product_qty: productQtyField.value,
      }).then(function (data) {
        alert(data.status);
      });
    });
  }

  if (wishButton && productIdField) {
    wishButton.addEventListener("click", function () {
      postJson("/addtofav/", { product_id: productIdField.value }).then(function (data) {
        alert(data.status);
      });
    });
  }

  if (notificationBadge && notificationList) {
    window.setInterval(function () {
      fetch("/notifications/json/")
        .then(function (response) {
          if (!response.ok) {
            throw new Error("Notifications unavailable");
          }
          return response.json();
        })
        .then(function (data) {
          notificationBadge.textContent = data.count;
          notificationBadge.classList.toggle("d-none", !data.count);
          notificationList.innerHTML = data.notifications.length
            ? data.notifications.map(function (item) {
                return '<a class="notification-item' + (item.is_read ? '' : ' notification-unread') + '" href="' +
                  (item.link || '#') + '"><strong>' + item.title + '</strong><span>' + item.message + '</span></a>';
              }).join("")
            : '<div class="notification-empty">No updates yet.</div>';
        })
        .catch(function () {});
    }, 30000);
  }
});
