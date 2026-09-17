/**
 * Renderitzador natiu de blocs MakeCode Arcade per a Jekyll i Just the Docs.
 * Converteix blocs de codi ```blocks ... ``` en SVG vectorials de blocs oficials.
 */
(function () {
  var targetUrl = "https://arcade.makecode.com/";
  var pendingPres = [];
  var iframeReady = false;

  function injectRenderer() {
    if (document.getElementById("makecoderenderer")) return;
    var f = document.createElement("iframe");
    f.id = "makecoderenderer";
    f.style.position = "absolute";
    f.style.left = "-9999px";
    f.style.top = "-9999px";
    f.style.width = "1px";
    f.style.height = "1px";
    f.src = targetUrl + "--docs?render=1";
    document.body.appendChild(f);
  }

  function renderPre(pre, idx) {
    if (!pre.id) {
      pre.id = "makecode-block-" + idx + "-" + Math.random().toString(36).substring(2, 8);
    }
    var f = document.getElementById("makecoderenderer");
    if (!iframeReady) {
      pendingPres.push(pre);
      injectRenderer();
    } else {
      f.contentWindow.postMessage(
        {
          type: "renderblocks",
          id: pre.id,
          code: pre.innerText || pre.textContent,
        },
        targetUrl
      );
    }
  }

  window.addEventListener(
    "message",
    function (ev) {
      var msg = ev.data;
      if (!msg || msg.source !== "makecode") return;

      if (msg.type === "renderready") {
        iframeReady = true;
        var pres = pendingPres.slice();
        pendingPres = [];
        pres.forEach(function (pre, idx) {
          renderPre(pre, idx);
        });
      } else if (msg.type === "renderblocks") {
        var id = msg.id;
        var code = document.getElementById(id);
        if (!code) return;

        var img = document.createElement("img");
        img.src = msg.uri;
        img.className = "makecode-rendered-blocks";
        img.alt = "Blocs de MakeCode Arcade";
        img.loading = "lazy";

        var container =
          code.closest(".highlighter-rouge") ||
          code.closest("pre") ||
          code;
        container.parentNode.insertBefore(img, container);
        container.parentNode.removeChild(container);
      }
    },
    false
  );

  function init() {
    var blocks = document.querySelectorAll(
      ".language-blocks code, pre > code.language-blocks, code[class*='language-blocks']"
    );
    if (blocks.length > 0) {
      injectRenderer();
      blocks.forEach(function (el, idx) {
        renderPre(el, idx);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
