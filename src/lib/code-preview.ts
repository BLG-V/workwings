/** 从模型 Markdown 输出中抽取可在 iframe / 新窗口里运行的 HTML */

export type FenceBlock = { lang: string; code: string }

function fenceBlocks(markdown: string): FenceBlock[] {
  const blocks: FenceBlock[] = []
  const re = /```([\w+-]*)\s*\n([\s\S]*?)```/g
  let m: RegExpExecArray | null
  while ((m = re.exec(markdown))) {
    blocks.push({
      lang: (m[1] || '').toLowerCase().trim(),
      code: m[2].replace(/\n$/, ''),
    })
  }
  return blocks
}

function scorePlayableHtml(code: string): number {
  let s = 0
  if (/<!doctype html/i.test(code) || /<html[\s>]/i.test(code)) s += 5
  if (/<canvas/i.test(code)) s += 3
  if (/keydown|keyup|KeyboardEvent/i.test(code)) s += 3
  if (/requestAnimationFrame|setInterval/i.test(code)) s += 2
  if (/getContext\s*\(\s*['"]2d['"]/i.test(code)) s += 2
  if (/<script/i.test(code)) s += 1
  return s
}

function wrapDocument(parts: {
  html?: string
  css?: string
  js?: string
  title?: string
}): string {
  const body = parts.html?.trim() || '<canvas id="game" width="400" height="400" tabindex="0"></canvas>'
  const looksFull =
    /<!doctype html/i.test(body) || /<html[\s>]/i.test(body)
  if (looksFull) {
    let doc = body
    if (parts.css && !/<style[\s>]/i.test(doc)) {
      doc = doc.replace(/<\/head>/i, `<style>${parts.css}</style></head>`)
      if (!/<\/head>/i.test(doc)) doc = `<style>${parts.css}</style>` + doc
    }
    if (parts.js && !/<script[\s>]/i.test(doc)) {
      doc = doc.replace(/<\/body>/i, `<script>${parts.js}<\/script></body>`)
      if (!/<\/body>/i.test(doc)) doc = doc + `<script>${parts.js}<\/script>`
    }
    return doc
  }

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${parts.title || '智流预览'}</title>
<style>
  html, body { margin: 0; min-height: 100%; height: 100%; background: #0b1220; color: #e8eaed; font-family: system-ui, sans-serif; }
  body { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 16px; box-sizing: border-box; }
  canvas, #game { background: #111827; border-radius: 12px; max-width: 100%; outline: none; box-shadow: 0 8px 30px rgba(0,0,0,.35); }
  #app { width: min(920px, 100%); }
  ${parts.css || ''}
</style>
</head>
<body>
${body}
<script>
try {
${parts.js || ''}
} catch (err) {
  document.body.insertAdjacentHTML('beforeend', '<pre style="color:#fca5a5;white-space:pre-wrap;max-width:90%">'+ String(err) +'</pre>');
}
<\/script>
</body>
</html>`
}

/** 轻量助手：不挡画面；补齐 canvas 可聚焦；暴露给父页面的按键注入 */
function injectPreviewHelpers(html: string): string {
  const helper = `
<style id="mawp-preview-helper-style">
  html, body { min-height: 100%; }
  canvas, #game { outline: none; }
  #mawp-preview-badge{
    position:fixed;left:12px;bottom:12px;z-index:99999;
    background:rgba(15,23,42,.82);color:#e2e8f0;border:1px solid rgba(148,163,184,.35);
    border-radius:999px;padding:6px 10px;font:12px/1.2 system-ui,sans-serif;
    pointer-events:none;opacity:.9
  }
</style>
<div id="mawp-preview-badge">游戏已加载 · 点画面后用键盘，或用外侧方向键</div>
<script>
(function(){
  function focusPlay(){
    var c = document.querySelector('canvas,#game,button,[tabindex]');
    if(c){
      try { c.setAttribute('tabindex','0'); c.focus({preventScroll:true}); } catch(e) {}
    }
    try { window.focus(); } catch(e) {}
  }
  document.addEventListener('pointerdown', focusPlay, true);
  window.addEventListener('load', function(){
    focusPlay();
    var cv = document.querySelector('canvas');
    if(cv){
      var rect = cv.getBoundingClientRect();
      if((!cv.width || cv.width < 2) && rect.width > 2) cv.width = Math.floor(rect.width);
      if((!cv.height || cv.height < 2) && rect.height > 2) cv.height = Math.floor(rect.height);
      if(!cv.width) cv.width = 320;
      if(!cv.height) cv.height = 480;
    }
  });
  // 父页面可注入按键（弹窗焦点陷阱时用）
  window.__mawpInjectKey = function(type, key, code){
    var init = {
      key: key,
      code: code || key,
      keyCode: key === ' ' ? 32 : (key.indexOf('Arrow')===0 ? ({ArrowLeft:37,ArrowUp:38,ArrowRight:39,ArrowDown:40})[key] : key.toUpperCase().charCodeAt(0)),
      which: key === ' ' ? 32 : (key.indexOf('Arrow')===0 ? ({ArrowLeft:37,ArrowUp:38,ArrowRight:39,ArrowDown:40})[key] : key.toUpperCase().charCodeAt(0)),
      bubbles: true,
      cancelable: true,
      view: window
    };
    var ev = new KeyboardEvent(type, init);
    try { Object.defineProperty(ev, 'keyCode', { get: function(){ return init.keyCode; } }); } catch(e) {}
    document.dispatchEvent(ev);
    window.dispatchEvent(ev);
    var active = document.activeElement || document.body;
    if(active && active.dispatchEvent) active.dispatchEvent(ev);
  };
  setTimeout(focusPlay, 50);
  setTimeout(focusPlay, 300);
})();
<\/script>`

  if (/<\/body>/i.test(html)) {
    return html.replace(/<\/body>/i, `${helper}</body>`)
  }
  return html + helper
}

export type PreviewBuild =
  | { ok: true; html: string; mode: string }
  | { ok: false; reason: string }

export function buildCodePreview(markdown: string): PreviewBuild {
  const text = (markdown || '').trim()
  if (!text) return { ok: false, reason: '还没有可预览的代码' }

  const blocks = fenceBlocks(text)
  const htmlBlocks = blocks.filter((b) =>
    ['html', 'htm', 'vue', 'svelte'].includes(b.lang),
  )
  const htmlBlock = [...htmlBlocks].sort(
    (a, b) => scorePlayableHtml(b.code) - scorePlayableHtml(a.code),
  )[0]
  const cssBlock = blocks.find((b) => ['css', 'scss'].includes(b.lang))
  const jsBlock = blocks.find((b) =>
    ['javascript', 'js', 'typescript', 'ts', 'jsx', 'tsx'].includes(b.lang),
  )

  if (htmlBlock) {
    const raw = htmlBlock.code
    if (/<!doctype html/i.test(raw) || /<html[\s>]/i.test(raw)) {
      return { ok: true, html: injectPreviewHelpers(raw), mode: '完整 HTML' }
    }
    return {
      ok: true,
      html: injectPreviewHelpers(
        wrapDocument({
          html: raw,
          css: cssBlock?.code,
          js: jsBlock?.code,
        }),
      ),
      mode: 'HTML + 样式/脚本',
    }
  }

  if (jsBlock) {
    const js = jsBlock.code
    const needsCanvas = /getContext\s*\(\s*['"]2d['"]\s*\)|canvas/i.test(js)
    return {
      ok: true,
      html: injectPreviewHelpers(
        wrapDocument({
          html: needsCanvas
            ? '<canvas id="game" width="400" height="400" tabindex="0"></canvas>'
            : '<div id="app" tabindex="0"></div>',
          css: cssBlock?.code,
          js: needsCanvas
            ? `const canvas = document.getElementById('game');\nconst __cv = canvas;\n${js}`
            : js,
        }),
      ),
      mode: needsCanvas ? 'Canvas 小游戏预览' : '脚本预览',
    }
  }

  if (/<!doctype html/i.test(text) || /<html[\s>]/i.test(text)) {
    return { ok: true, html: injectPreviewHelpers(text), mode: '完整 HTML' }
  }

  return {
    ok: false,
    reason:
      '当前结果里没有可直接运行的 HTML/JS。可让模型重新生成「单文件可运行 HTML」，或复制代码到本地运行。',
  }
}

export function createPreviewObjectUrl(html: string): string {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  return URL.createObjectURL(blob)
}
