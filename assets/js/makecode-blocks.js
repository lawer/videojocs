/**
 * Renderitzador natiu de blocs MakeCode Arcade per a Jekyll i Just the Docs.
 *
 * Estratègia d'alt rendiment:
 * 1. Comprova si el bloc ja està pre-renderitzat a 'assets/images/blocks/<hash>.png'
 *    i el carrega a l'instant (0 ms) sense tocar els servidors de MakeCode.
 * 2. Si la imatge estàtica no existeix (p. ex. codi nou sense pre-renderitzar),
 *    activa automàticament l'iframe oficial de MakeCode com a fallback dinàmic.
 */
(function () {
  var targetUrl = "https://arcade.makecode.com/";
  var pendingPres = [];
  var iframeReady = false;

  // Determinar la URL base del lloc dinàmicament
  var scriptEl =
    document.currentScript ||
    document.querySelector('script[src*="makecode-blocks.js"]');
  var baseUrl = "";
  if (scriptEl && scriptEl.src) {
    var src = scriptEl.src;
    var idx = src.indexOf("/assets/js/makecode-blocks.js");
    if (idx !== -1) {
      baseUrl = src.substring(0, idx);
    }
  }

  // Càlcul ràpid i autònom de SHA-256 en pur JavaScript
  function sha256(ascii) {
    function rightRotate(value, amount) {
      return (value >>> amount) | (value << (32 - amount));
    }
    var mathPow = Math.pow;
    var maxWord = mathPow(2, 32);
    var lengthProperty = "length";
    var i, j;
    var result = "";
    var words = [];
    var asciiBitLength = ascii[lengthProperty] * 8;
    var hash = [];
    var k = [];
    var primeCounter = 0;
    var isComposite = {};
    for (var candidate = 2; primeCounter < 64; candidate++) {
      if (!isComposite[candidate]) {
        for (i = 0; i < 313; i += candidate) {
          isComposite[i] = candidate;
        }
        hash[primeCounter] = (mathPow(candidate, 0.5) * maxWord) | 0;
        k[primeCounter++] = (mathPow(candidate, 1 / 3) * maxWord) | 0;
      }
    }
    ascii += "\x80";
    while ((ascii[lengthProperty] % 64) - 56) ascii += "\x00";
    for (i = 0; i < ascii[lengthProperty]; i++) {
      j = ascii.charCodeAt(i);
      if (j >> 8) return;
      words[i >> 2] |= j << ((3 - i) % 4) * 8;
    }
    words[words[lengthProperty]] = (asciiBitLength / maxWord) | 0;
    words[words[lengthProperty]] = asciiBitLength;
    for (j = 0; j < words[lengthProperty]; ) {
      var w = words.slice(j, (j += 16));
      var oldHash = hash;
      hash = hash.slice(0, 8);
      for (i = 0; i < 64; i++) {
        var i2 = i + j;
        var w15 = w[i - 15],
          w2 = w[i - 2];
        var a = hash[0],
          e = hash[4];
        var temp1 =
          hash[7] +
          (rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25)) +
          ((e & hash[5]) ^ (~e & hash[6])) +
          k[i] +
          (w[i] =
            i < 16
              ? w[i]
              : (w[i - 16] +
                  (rightRotate(w15, 7) ^
                    rightRotate(w15, 18) ^
                    (w15 >>> 3)) +
                  w[i - 7] +
                  (rightRotate(w2, 17) ^
                    rightRotate(w2, 19) ^
                    (w2 >>> 10))) |
                0);
        var temp2 =
          (rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22)) +
          ((a & hash[1]) ^ (a & hash[2]) ^ (hash[1] & hash[2]));
        hash = [(temp1 + temp2) | 0].concat(hash);
        hash[4] = (hash[4] + temp1) | 0;
      }
      for (i = 0; i < 8; i++) {
        hash[i] = (hash[i] + oldHash[i]) | 0;
      }
    }
    for (i = 0; i < 8; i++) {
      for (i2 = 3; i2 >= 0; i2--) {
        var c = (hash[i] >> (i2 * 8)) & 255;
        result += (c < 16 ? "0" : "") + c.toString(16);
      }
    }
    return result;
  }

  function utf8Encode(str) {
    return unescape(encodeURIComponent(str));
  }

  function normalizeCode(rawCode) {
    var isSnippet = false;
    if (
      /\/\/\s*(snippet|standalone|nostart|no-start)/i.test(rawCode)
    ) {
      isSnippet = true;
      rawCode = rawCode
        .replace(/\/\/\s*(snippet|standalone|nostart|no-start)[^\r\n]*/gi, "")
        .trim();
    }

    var lines = rawCode
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .split("\n")
      .map(function (l) {
        return l.trimEnd();
      });

    while (lines.length && lines[0] === "") lines.shift();
    while (lines.length && lines[lines.length - 1] === "") lines.pop();

    var normalized = lines.join("\n");
    var prefix = isSnippet ? "snippet:" : "full:";
    var hash = sha256(utf8Encode(prefix + normalized)).substring(0, 16);

    return {
      hash: hash,
      isSnippet: isSnippet,
      code: normalized,
    };
  }

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

  function renderPreDynamic(pre, idx, norm) {
    if (!pre.id) {
      pre.id =
        "makecode-block-" + idx + "-" + Math.random().toString(36).substring(2, 8);
    }
    var payload = {
      type: "renderblocks",
      id: pre.id,
      code: norm.code,
    };
    if (norm.isSnippet) {
      payload.options = { snippetMode: true };
    }

    var f = document.getElementById("makecoderenderer");
    if (!iframeReady) {
      pendingPres.push({ pre: pre, payload: payload });
      injectRenderer();
    } else {
      f.contentWindow.postMessage(payload, targetUrl);
    }
  }

  function reorderPngBlocks(dataUri, callback) {
    if (
      typeof dataUri !== "string" ||
      dataUri.indexOf("data:image/png") === -1
    ) {
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

        var startSliceIdx = -1;
        for (var i = 0; i < slices.length; i++) {
          var s = slices[i];
          var headerGreenCount = 0;
          var headerMaxY = Math.min(s.y2, s.y1 + 80);
          var headerMaxX = Math.min(w, 600);
          for (var sy = s.y1; sy <= headerMaxY; sy++) {
            var offset = sy * w * 4;
            for (var sx = 0; sx < headerMaxX; sx++) {
              var r = data[offset + sx * 4];
              var g = data[offset + sx * 4 + 1];
              var b = data[offset + sx * 4 + 2];
              var a = data[offset + sx * 4 + 3];
              if (a > 200 && r < 50 && g > 140 && b < 100) {
                headerGreenCount++;
              }
            }
          }
          if (headerGreenCount > 500) {
            startSliceIdx = i;
            break;
          }
        }

        if (startSliceIdx <= 0) {
          callback(dataUri);
          return;
        }

        var reorderedSlices = [slices[startSliceIdx]];
        for (var j = 0; j < slices.length; j++) {
          if (j !== startSliceIdx) reorderedSlices.push(slices[j]);
        }

        var gap = slices.length > 1 ? slices[1].y1 - slices[0].y2 : 60;
        if (gap < 20) gap = 48;

        var totalHeight = 0;
        for (var k = 0; k < reorderedSlices.length; k++) {
          totalHeight += reorderedSlices[k].y2 - reorderedSlices[k].y1 + 1;
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

  // Missatges de l'iframe dinàmic (fallback)
  window.addEventListener(
    "message",
    function (ev) {
      var msg = ev.data;
      if (!msg || msg.source !== "makecode") return;

      if (msg.type === "renderready") {
        iframeReady = true;
        var pending = pendingPres.slice();
        pendingPres = [];
        var f = document.getElementById("makecoderenderer");
        if (f) {
          pending.forEach(function (item) {
            f.contentWindow.postMessage(item.payload, targetUrl);
          });
        }
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

  function processBlock(el, idx) {
    var rawCode = el.innerText || el.textContent;
    var norm = normalizeCode(rawCode);

    var container =
      el.closest(".highlighter-rouge") || el.closest("pre") || el;

    var staticImgUrl =
      baseUrl + "/assets/images/blocks/" + norm.hash + ".png";

    // Intentar carregar la imatge estàtica
    var img = document.createElement("img");
    img.className = "makecode-rendered-blocks";
    img.alt = "Blocs de MakeCode Arcade";

    // Si falla la càrrega estàtica (p. ex. bloc nou sense pre-renderitzar), fallback al renderitzat dinàmic
    img.onerror = function () {
      if (img.parentNode) {
        img.parentNode.insertBefore(container, img);
        img.parentNode.removeChild(img);
      }
      renderPreDynamic(el, idx, norm);
    };

    img.src = staticImgUrl;

    // Substitució immediata del contenidor de codi per la imatge
    if (container && container.parentNode) {
      container.parentNode.insertBefore(img, container);
      container.parentNode.removeChild(container);
    }
  }

  function init() {
    var blocks = document.querySelectorAll(
      ".language-blocks code, pre > code.language-blocks, code[class*='language-blocks']"
    );
    if (blocks.length > 0) {
      blocks.forEach(function (el, idx) {
        processBlock(el, idx);
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
