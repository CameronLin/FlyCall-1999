
(function () {
  // result charts: each .ch figure's buttons switch which .ch-pane is shown
  document.querySelectorAll(".ch").forEach(function (fig) {
    fig.querySelectorAll(".ch-seg button").forEach(function (b) {
      b.addEventListener("click", function () {
        var pane = b.getAttribute("data-pane");
        fig.querySelectorAll(".ch-seg button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        fig.querySelectorAll(".ch-pane").forEach(function (p) { p.hidden = p.getAttribute("data-pane") !== pane; });
      });
    });
  });
})();
