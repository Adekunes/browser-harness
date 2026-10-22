// Injected into every page when BH_STEALTH=1 (Page.addScriptToEvaluateOnNewDocument).
// Patches only signals current headless Chrome still leaks; webdriver, plugins and
// window.chrome are already native-correct, and re-patching them is itself detectable.
// Runs once per document even when several CDP sessions registered it.
(() => {
  const once = Symbol.for('bh.stealth');
  if (window[once]) return;
  Object.defineProperty(window, once, { value: true });

  // navigator.languages — headless reports only the primary locale.
  if (navigator.languages.length < 2) {
    const langs = Object.freeze([navigator.language, navigator.language.split('-')[0]]);
    Object.defineProperty(Navigator.prototype, 'languages', { get: () => langs, configurable: true });
  }

  // WebGL — headless renders with SwiftShader, a well-known automation tell.
  // 37445 = UNMASKED_VENDOR_WEBGL, 37446 = UNMASKED_RENDERER_WEBGL.
  for (const Ctx of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) {
    if (!Ctx) continue;
    const getParameter = Ctx.prototype.getParameter;
    Ctx.prototype.getParameter = function (p) {
      if ((p === 37445 || p === 37446) && /SwiftShader/i.test(getParameter.call(this, 37446))) {
        return p === 37445 ? 'Google Inc. (Intel)' : 'ANGLE (Intel, Intel(R) UHD Graphics 630 (0x00003E9B) Direct3D11 vs_5_0 ps_5_0, D3D11)';
      }
      return getParameter.apply(this, arguments);
    };
  }
})();
