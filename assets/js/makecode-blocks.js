/**
 * Renderitzador natiu de blocs MakeCode Arcade per a Jekyll i Just the Docs.
 * Converteix blocs de codi ```blocks ... ``` en SVG / PNG de blocs oficials.
 * Assegura que el bloc 'al iniciar' se situï a dalt de tot.
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

  function reorderPngBlocks(dataUri, callback) {
    if (typeof dataUri !== "string" || dataUri.indexOf("data:image/png") === -1) {
      callback(dataUri);
      return;
    }

    var img = new Image();
    img.onload = function () {
      try {
        var w = img.naturalWidth || img.width;
        var h = img.naturalHeight || img.height;
        var canvas = document.createElement("canvas");
        canvas.width = w;
        canvas.height = h;
        var ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0);

        var imgData = ctx.getImageData(0, 0, w, h);
        var data = imgData.data;

        // Check each row for non-transparent pixels
        var rowHasContent = new Uint8Array(h);
        for (var y = 0; y < h; y++) {
          var rowOffset = y * w * 4;
          for (var x = 0; x < w; x++) {
            if (data[rowOffset + x * 4 + 3] > 10) {
              rowHasContent[y] = 1;
              break;
            }
          }
        }

        // Find contiguous block slices separated by blank rows
        var slices = [];
        var inSlice = false;
        var startY = 0;
        for (var y = 0; y < h; y++) {
          if (rowHasContent[y] && !inSlice) {
            inSlice = true;
            startY = y;
          } else if (!rowHasContent[y] && inSlice) {
            inSlice = false;
            slices.push({ y1: startY, y2: y - 1 });
          }
        }
        if (inSlice) {
          slices.push({ y1: startY, y2: h - 1 });
        }

        if (slices.length <= 1) {
          callback(dataUri);
          return;
        }

        // Identify which slice contains the green 'al iniciar' block
        var startSliceIdx = -1;
        for (var i = 0; i < slices.length; i++) {
          var s = slices[i];
          var hasGreen = false;
          for (var sy = s.y1; sy <= s.y2 && !hasGreen; sy++) {
            var offset = sy * w * 4;
            for (var sx = 0; sx < w; sx++) {
              var r = data[offset + sx * 4];
              var g = data[offset + sx * 4 + 1];
              var b = data[offset + sx * 4 + 2];
              var a = data[offset + sx * 4 + 3];
              // MakeCode green is around RGB(0..50, 140..220, 0..100)
              if (a > 200 && r < 50 && g > 140 && b < 100) {
                hasGreen = true;
                break;
              }
            }
          }
          if (hasGreen) {
            startSliceIdx = i;
            break;
          }
        }

        // If 'al iniciar' is already first (0) or not found (-1), return original
        if (startSliceIdx <= 0) {
          callback(dataUri);
          return;
        }

        // Reorder: 'al iniciar' first, then the remaining slices
        var reorderedSlices = [slices[startSliceIdx]];
        for (var j = 0; j < slices.length; j++) {
          if (j !== startSliceIdx) reorderedSlices.push(slices[j]);
        }

        // Calculate gap from original layout
        var gap = slices.length > 1 ? (slices[1].y1 - slices[0].y2) : 60;
        if (gap < 20) gap = 48;

        var totalHeight = 0;
        for (var k = 0; k < reorderedSlices.length; k++) {
          totalHeight += (reorderedSlices[k].y2 - reorderedSlices[k].y1 + 1);
          if (k > 0) totalHeight += gap;
        }

        var outCanvas = document.createElement("canvas");
        outCanvas.width = w;
        outCanvas.height = totalHeight;
        var outCtx = outCanvas.getContext("2d");

        var curY = 0;
        for (var m = 0; m < reorderedSlices.length; m++) {
          var sl = reorderedSlices[m];
          var sliceH = sl.y2 - sl.y1 + 1;
          outCtx.drawImage(canvas, 0, sl.y1, w, sliceH, 0, curY, w, sliceH);
          curY += sliceH + gap;
        }

        callback(outCanvas.toDataURL("image/png"));
      } catch (err) {
        console.warn("reorderPngBlocks error:", err);
        callback(dataUri);
      }
    };
    img.onerror = function () {
      callback(dataUri);
    };
    img.src = dataUri;
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

        reorderPngBlocks(msg.uri, function (finalUri) {
          var img = document.createElement("img");
          img.src = finalUri;
          img.className = "makecode-rendered-blocks";
          img.alt = "Blocs de MakeCode Arcade";
          img.loading = "lazy";

          var container =
            code.closest(".highlighter-rouge") ||
            code.closest("pre") ||
            code;
          if (container && container.parentNode) {
            container.parentNode.insertBefore(img, container);
            container.parentNode.removeChild(container);
          }
        });
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
