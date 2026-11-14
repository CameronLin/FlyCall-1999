
(function () {
  var root = document.getElementById("training-time");
  if (!root) return;
  root.querySelectorAll(".tt-tb").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = b.getAttribute("data-tt");
      root.querySelectorAll(".tt-tb").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      root.querySelectorAll(".tt-pane").forEach(function (p) { p.hidden = p.getAttribute("data-tt") !== t; });
    });
  });
})();
