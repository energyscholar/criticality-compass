"""The style sheet and the script of the needle player: two string constants, no function.

The script shows, hides and interpolates elements that Python wrote. It computes no position of its own.
"""

STYLE = """
:root{--bg:#fbfbf8;--fg:#1d1f21;--mute:#6a6f76;--line:#c9ccd1;--a:#b3470f;--b:#14628a;--g0:#3a7d44;--g1:#7a4aa0;--next:#f2d37a;--zero:#8a8f96;--truth:#c0182f;--panel:#ffffff;--trail:#9fb7c8;--now:#14628a;--sysbg:#f6eef0}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#15171a;--fg:#e6e7e9;--mute:#9aa0a8;--line:#3a3f46;--a:#f09a62;--b:#6cb8e6;--g0:#7fcf8a;--g1:#c39be6;--next:#6b5a1d;--zero:#7d838b;--truth:#ff6b7d;--panel:#1d2024;--trail:#4a6275;--now:#6cb8e6;--sysbg:#2a2024}}
:root[data-theme="dark"]{--bg:#15171a;--fg:#e6e7e9;--mute:#9aa0a8;--line:#3a3f46;--a:#f09a62;--b:#6cb8e6;--g0:#7fcf8a;--g1:#c39be6;--next:#6b5a1d;--zero:#7d838b;--truth:#ff6b7d;--panel:#1d2024;--trail:#4a6275;--now:#6cb8e6;--sysbg:#2a2024}
[hidden]{display:none !important}
*{box-sizing:border-box}
body{margin:0;padding:12px 16px;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}
h1{font-size:1.2rem;margin:0 0 .3rem}
.mute{color:var(--mute);font-size:.8rem;margin:.2rem 0 .5rem}
.bar,.controls{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:.3rem 0}
select,button,input,output{font:inherit;color:var(--fg);background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:2px 8px;max-width:100%}
select{min-width:0}
input[type=range]{flex:1 1 120px;min-width:80px;padding:0}
button{cursor:pointer}
button:disabled{opacity:.45;cursor:default}
section.run{display:flex;flex-wrap:wrap;gap:6px;margin-top:.4rem}
.round{display:contents}
.head,.outcome,.unreadable,.body{flex:0 0 100%}
.head{order:0}
button.rnd{order:1;min-width:2.2rem}
button.rnd.on{background:var(--now);color:var(--bg);border-color:var(--now)}
.body,.round>svg.frame{order:2}
.round>svg.frame{flex:0 0 100%}
.outcome,.unreadable{order:3}
.head,.outcome{display:flex;flex-wrap:wrap;gap:8px}
.zone{flex:1 1 150px;min-width:0;padding:4px 8px;border-radius:4px}
.zone[data-source="navigator"]{border:2px solid var(--fg);background:var(--panel)}
.zone[data-source="system"]{border:2px dashed var(--truth);background:var(--sysbg)}
.zone-name{display:block;font-size:.7rem;letter-spacing:.08em;font-weight:700;color:var(--mute)}
.row{display:flex;justify-content:space-between;gap:8px;font-size:.85rem;overflow-wrap:anywhere}
.cap{color:var(--mute)}
.slot{font-variant-numeric:tabular-nums;text-align:right}
.slot[data-state="unknown"]{font-style:italic;letter-spacing:.04em;color:var(--truth)}
.slot[data-state="absent"],.slot[data-state="not-reported"]{color:var(--mute)}
.why{margin:0;color:var(--truth);overflow-wrap:anywhere}
svg.frame{--w:min(84%,calc((100vh - 140px)*.9375));display:block;overflow:visible;width:var(--w);max-width:none;height:auto;margin:0 0 calc(var(--w)*.04) calc(var(--w)*.17);background:var(--panel);border:1px solid var(--line)}
svg.frame text{fill:var(--mute);font-size:9px}
svg.frame text.axis-title{fill:var(--fg);font-size:8px;font-weight:600}
svg.frame text.sys-unknown{fill:var(--truth);font-style:italic}
rect.box{fill:none;stroke:var(--line)}
line.tick{stroke:var(--mute);stroke-width:1}
line.zero{stroke:var(--zero);stroke-dasharray:3 2}
rect.next{fill:var(--next);opacity:.45}
rect.trail{fill:var(--trail);stroke:var(--line);opacity:.8}
rect.trail.now{fill:var(--now);opacity:1}
line.c-err,line.d-err{stroke:var(--mute);stroke-width:1}
circle.c,circle.d{stroke-width:1.5;fill:none}
circle.c{stroke:var(--a)}circle.c.in-A{fill:var(--a);stroke-width:3}
circle.d{stroke:var(--b)}circle.d.in-B{fill:var(--b);stroke-width:3}
circle.g{stroke-width:1.2}
circle.g.l0{fill:var(--g0);stroke:var(--g0)}circle.g.l1{fill:none;stroke:var(--g1)}circle.g.l2{fill:var(--mute);stroke:var(--mute)}
line.truth{stroke:var(--truth);stroke-width:1.5;stroke-dasharray:4 2}
polygon.truth-off{fill:var(--truth)}
#speed{flex:0 1 90px;min-width:60px}
.controls label{display:inline-flex;align-items:center;gap:4px}
#full{padding:4px 8px}
#full .ico{display:inline-block;width:14px;height:14px;vertical-align:middle;background:linear-gradient(currentColor,currentColor) left top/5px 2px no-repeat,linear-gradient(currentColor,currentColor) left top/2px 5px no-repeat,linear-gradient(currentColor,currentColor) right top/5px 2px no-repeat,linear-gradient(currentColor,currentColor) right top/2px 5px no-repeat,linear-gradient(currentColor,currentColor) left bottom/5px 2px no-repeat,linear-gradient(currentColor,currentColor) left bottom/2px 5px no-repeat,linear-gradient(currentColor,currentColor) right bottom/5px 2px no-repeat,linear-gradient(currentColor,currentColor) right bottom/2px 5px no-repeat}
:root.fs-on{overflow:hidden}
#player.fs-on{position:fixed;inset:0;z-index:1000;overflow:auto;margin:0;padding:8px 16px;background:var(--bg)}
#player.fs-on svg.frame{--w:min(84%,calc(max(200px,100vh - 446px)*.9375))}
@media (max-width: 600px){#player.fs-on svg.frame{--w:min(84%,calc(max(200px,100vh - 654px)*.9375))}}
@media (prefers-reduced-motion: reduce){*{transition:none !important;animation:none !important;scroll-behavior:auto !important}}
"""

SCRIPT = """
(function () {
  var player = document.getElementById('player');
  var stage = document.getElementById('stage');
  var pickWorld = document.getElementById('pick-world');
  var prevB = document.getElementById('prev');
  var playB = document.getElementById('play');
  var nextB = document.getElementById('next');
  var scrub = document.getElementById('scrub');
  var pos = document.getElementById('pos');
  var speed = document.getElementById('speed');
  var loopBox = document.getElementById('loop');
  var allBox = document.getElementById('all');
  var fullBtn = document.getElementById('full');
  var rootEl = document.documentElement;
  var stepMs = parseFloat(player.getAttribute('data-step-ms'));
  var playMs = parseFloat(player.getAttribute('data-play-ms'));
  var still = window.matchMedia('(prefers-reduced-motion: reduce)');
  var MOVING = ['cx', 'cy', 'x', 'y', 'x1', 'x2', 'y1', 'y2', 'width', 'height'];
  var pending = null;
  var playing = false;
  var clock = null;
  var fsOn = false;

  function all(root, selector) {
    return root.querySelectorAll(selector);
  }

  function shownRun() {
    var secs = all(stage, 'section.run');
    var i;
    for (i = 0; i < secs.length; i = i + 1) {
      if (!secs[i].hidden) { return secs[i]; }
    }
    return null;
  }

  function currentRound(sec) {
    var btns = all(sec, 'button.rnd');
    var i;
    for (i = 0; i < btns.length; i = i + 1) {
      if (btns[i].classList.contains('on')) { return i + 1; }
    }
    return 0;
  }

  function pace() {
    return parseFloat(speed.value);
  }

  function refresh() {
    var sec = shownRun();
    var n = 0;
    var cur = 0;
    if (sec) {
      n = all(sec, 'div.round').length;
      cur = currentRound(sec);
    }
    if (n === 0) {
      scrub.disabled = true;
      prevB.disabled = true;
      nextB.disabled = true;
      playB.disabled = !allBox.checked;
      pos.textContent = 'no rounds';
      return;
    }
    scrub.disabled = false;
    playB.disabled = false;
    scrub.max = String(n);
    scrub.value = String(cur);
    prevB.disabled = cur <= 1;
    nextB.disabled = cur >= n;
    pos.textContent = 'round ' + cur + ' of ' + n;
  }

  function markOn(sec, n) {
    var btns = all(sec, 'button.rnd');
    var i;
    for (i = 0; i < btns.length; i = i + 1) {
      if (i + 1 === n) { btns[i].classList.add('on'); } else { btns[i].classList.remove('on'); }
    }
  }

  function bodyOf(sec, n) {
    return all(sec, 'div.round')[n - 1].querySelector('div.body');
  }

  function settle() {
    var p = pending;
    if (!p) { return; }
    pending = null;
    p.clone.parentNode.removeChild(p.clone);
    p.fromSvg.removeAttribute('hidden');
    p.from.hidden = true;
    p.to.hidden = false;
  }

  function stopPlay() {
    playing = false;
    clock = null;
    playB.textContent = 'play';
    playB.setAttribute('aria-pressed', 'false');
  }

  function pairs(clone, target) {
    var found = {};
    var theirs = all(target, '[data-key]');
    var mine = all(clone, '[data-key]');
    var out = [];
    var i;
    var j;
    var key;
    var name;
    for (i = 0; i < theirs.length; i = i + 1) {
      found[theirs[i].getAttribute('data-key')] = theirs[i];
    }
    for (i = 0; i < mine.length; i = i + 1) {
      key = mine[i].getAttribute('data-key');
      if (found[key]) {
        for (j = 0; j < MOVING.length; j = j + 1) {
          name = MOVING[j];
          if (mine[i].hasAttribute(name) && found[key].hasAttribute(name)) {
            out.push({ el: mine[i], name: name, a: parseFloat(mine[i].getAttribute(name)), b: parseFloat(found[key].getAttribute(name)) });
          }
        }
      }
    }
    return out;
  }

  function ease(t) {
    return t * t * (3 - 2 * t);
  }

  function goTo(n) {
    var sec = shownRun();
    var rounds;
    var cur;
    var from;
    var fromSvg;
    var to;
    var clone;
    var moves;
    var started = null;
    var mine;
    if (!sec) { return; }
    rounds = all(sec, 'div.round').length;
    if (n < 1 || n > rounds) { return; }
    settle();
    cur = currentRound(sec);
    if (cur === n) { refresh(); return; }
    to = bodyOf(sec, n);
    markOn(sec, n);
    refresh();
    if (cur === 0 || still.matches) {
      if (cur > 0) { bodyOf(sec, cur).hidden = true; }
      to.hidden = false;
      return;
    }
    from = bodyOf(sec, cur);
    fromSvg = from.querySelector('svg');
    clone = fromSvg.cloneNode(true);
    moves = pairs(clone, to.querySelector('svg'));
    fromSvg.parentNode.insertBefore(clone, fromSvg);
    fromSvg.setAttribute('hidden', '');
    mine = { clone: clone, to: to, from: from, fromSvg: fromSvg };
    pending = mine;
    function frame(ts) {
      var t;
      var k;
      var e;
      if (pending !== mine) { return; }
      if (started === null) { started = ts; }
      t = (ts - started) * pace() / stepMs;
      if (t >= 1) { settle(); return; }
      e = ease(t);
      for (k = 0; k < moves.length; k = k + 1) {
        moves[k].el.setAttribute(moves[k].name, String(moves[k].a + (moves[k].b - moves[k].a) * e));
      }
      window.requestAnimationFrame(frame);
    }
    window.requestAnimationFrame(frame);
  }

  function showRun(sec) {
    var secs = all(stage, 'section.run');
    var bodies = all(stage, 'div.body');
    var btns = all(stage, 'button.rnd');
    var i;
    settle();
    for (i = 0; i < secs.length; i = i + 1) { secs[i].hidden = secs[i] !== sec; }
    for (i = 0; i < bodies.length; i = i + 1) { bodies[i].hidden = true; }
    for (i = 0; i < btns.length; i = i + 1) { btns[i].classList.remove('on'); }
    if (sec && all(sec, 'div.round').length > 0) {
      markOn(sec, 1);
      bodyOf(sec, 1).hidden = false;
    }
    refresh();
  }

  function chooseRun(select) {
    var secs = all(stage, 'section.run');
    var i;
    for (i = 0; i < secs.length; i = i + 1) {
      if (secs[i].getAttribute('data-run') === select.value) { showRun(secs[i]); return; }
    }
    showRun(null);
  }

  function chooseWorld(first) {
    var selects = all(player, 'select.pick-run');
    var chosen = null;
    var i;
    for (i = 0; i < selects.length; i = i + 1) {
      selects[i].hidden = selects[i].getAttribute('data-world') !== pickWorld.value;
      if (!selects[i].hidden) { chosen = selects[i]; }
    }
    if (chosen) {
      if (first) { chosen.selectedIndex = 0; }
      chooseRun(chosen);
    } else { showRun(null); }
  }

  function shownSelect() {
    var selects = all(player, 'select.pick-run');
    var i;
    for (i = 0; i < selects.length; i = i + 1) {
      if (!selects[i].hidden) { return selects[i]; }
    }
    return null;
  }

  function nextRun() {
    var sel = shownSelect();
    if (!sel) { return false; }
    if (sel.selectedIndex + 1 < sel.options.length) {
      sel.selectedIndex = sel.selectedIndex + 1;
      chooseRun(sel);
      return true;
    }
    if (pickWorld.selectedIndex + 1 < pickWorld.options.length) {
      pickWorld.selectedIndex = pickWorld.selectedIndex + 1;
      chooseWorld(true);
      return true;
    }
    if (loopBox.checked) {
      pickWorld.selectedIndex = 0;
      chooseWorld(true);
      return true;
    }
    return false;
  }

  function loop(ts) {
    var sec;
    var cur;
    var n;
    if (!playing) { return; }
    if (clock === null) { clock = ts; }
    if ((ts - clock) * pace() >= playMs) {
      clock = ts;
      sec = shownRun();
      cur = sec ? currentRound(sec) : 0;
      n = sec ? all(sec, 'div.round').length : 0;
      if (cur < n) {
        goTo(cur + 1);
        if (cur + 1 >= n && !loopBox.checked && !allBox.checked) { stopPlay(); return; }
      } else if (allBox.checked) {
        if (!nextRun()) { stopPlay(); return; }
      } else if (loopBox.checked && n > 0) {
        goTo(1);
      } else { stopPlay(); return; }
    }
    window.requestAnimationFrame(loop);
  }

  function togglePlay() {
    var sec = shownRun();
    var n = sec ? all(sec, 'div.round').length : 0;
    if (playing) { stopPlay(); return; }
    if (!sec || (n === 0 && !allBox.checked)) { return; }
    if (n > 0 && currentRound(sec) >= n) { goTo(1); }
    playing = true;
    clock = null;
    playB.textContent = 'pause';
    playB.setAttribute('aria-pressed', 'true');
    window.requestAnimationFrame(loop);
  }

  function step(by) {
    var sec = shownRun();
    if (sec) { goTo(currentRound(sec) + by); }
  }

  function setFull(on) {
    fsOn = on;
    if (on) {
      player.classList.add('fs-on');
      rootEl.classList.add('fs-on');
    } else {
      player.classList.remove('fs-on');
      rootEl.classList.remove('fs-on');
    }
    fullBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
  }

  function quietly(promise) {
    if (promise && promise.then) { promise.then(null, function () {}); }
  }

  function leaveBrowserFull() {
    if (document.fullscreenElement && document.exitFullscreen) {
      try { quietly(document.exitFullscreen()); } catch (err) { }
    }
  }

  function enterFull() {
    setFull(true);
    if (player.requestFullscreen) {
      try { quietly(player.requestFullscreen()); } catch (err) { }
    }
  }

  function leaveFull() {
    if (!fsOn) { return; }
    setFull(false);
    leaveBrowserFull();
  }

  fullBtn.addEventListener('click', function () {
    if (fsOn) { leaveFull(); } else { enterFull(); }
  });
  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { leaveFull(); }
  });
  document.addEventListener('fullscreenchange', function () {
    if (!document.fullscreenElement) { leaveFull(); } else if (!fsOn) { leaveBrowserFull(); }
  });

  player.addEventListener('change', function (ev) {
    if (ev.target === pickWorld) { stopPlay(); chooseWorld(); }
    if (ev.target.classList.contains('pick-run')) { stopPlay(); chooseRun(ev.target); }
    if (ev.target === allBox) { refresh(); }
  });
  prevB.addEventListener('click', function () { stopPlay(); step(-1); });
  nextB.addEventListener('click', function () { stopPlay(); step(1); });
  playB.addEventListener('click', togglePlay);
  scrub.addEventListener('input', function () { stopPlay(); goTo(Number(scrub.value)); });
  stage.addEventListener('click', function (ev) {
    if (ev.target.classList.contains('rnd')) { stopPlay(); goTo(Number(ev.target.getAttribute('data-round'))); }
  });
  chooseWorld();
}());
"""
