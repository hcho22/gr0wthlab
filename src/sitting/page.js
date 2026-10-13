// The sitting page's own script. It only helps the Founder see what is about to be sent: it counts the characters of
// a one-line field, keeps the sitting's clock moving, and stops a form from being sent twice. It never sends, fills,
// or chooses anything by itself, and the page works without it.
(function () {
  "use strict";

  // A line holds at most its maxlength; say how many characters are left once the line is getting long.
  document.querySelectorAll("input[data-counted]").forEach(function (input) {
    var most = Number(input.getAttribute("maxlength")) || 300;
    var counter = document.createElement("span");
    counter.className = "counter";
    counter.setAttribute("aria-live", "polite");
    input.insertAdjacentElement("afterend", counter);
    function count() {
      var used = input.value.length;
      counter.textContent = used > most - 100 ? used + " of " + most + " characters" : "";
      counter.classList.toggle("full", used >= most);
    }
    input.addEventListener("input", count);
    count();
  });

  // The clock shows the minutes the page had measured when it was drawn, plus the minutes since.
  var clock = document.querySelector(".clock[data-minutes]");
  if (clock) {
    var drawn = Date.now();
    var measured = Number(clock.getAttribute("data-minutes")) || 1;
    setInterval(function () {
      clock.textContent = measured + Math.floor((Date.now() - drawn) / 60000) + " min";
    }, 15000);
  }

  // One click, one request: a form that was sent cannot be sent again from the same page.
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function (event) {
      if (form.getAttribute("data-sent")) {
        event.preventDefault();
        return;
      }
      form.setAttribute("data-sent", "1");
      form.querySelectorAll("button").forEach(function (button) {
        button.setAttribute("aria-disabled", "true");
      });
    });
  });
})();
