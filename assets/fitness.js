(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.DoubleJumpFitness = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  var LIN = ["s", "l", "p", "g"], DRIFT = ["x", "z"], N = 100, STRESS_LIMIT = 12;

  function sorted(k) { return (k || []).slice().sort(function (a, b) { return a.at - b.at; }); }
  function sampleAt(s, at) {
    if (!s.length) return {};
    if (at <= s[0].at) return s[0];
    if (at >= s[s.length - 1].at) return s[s.length - 1];
    for (var i = 0; i < s.length - 1; i++) {
      var a = s[i], b = s[i + 1];
      if (a.at <= at && at <= b.at) {
        var t = (at - a.at) / ((b.at - a.at) || 1), out = {};
        LIN.concat(DRIFT).forEach(function (field) {
          out[field] = (a[field] || 0) + ((b[field] || 0) - (a[field] || 0)) * t;
        });
        return out;
      }
    }
    return s[s.length - 1];
  }
  function expand(moment) {
    var s = sorted(moment.k), out = [];
    for (var i = 0; i < N; i++) out.push(sampleAt(s, i / (N - 1) * 99));
    return out;
  }
  function mean(values) {
    return values.reduce(function (sum, value) { return sum + value; }, 0) / (values.length || 1);
  }
  function std(values) {
    var average = mean(values);
    return Math.sqrt(mean(values.map(function (value) { return Math.pow(value - average, 2); })));
  }
  function frameKey(frame) {
    return LIN.concat(DRIFT).map(function (field) { return +(frame[field] || 0).toFixed(4); }).join("|");
  }
  function vitality(moment) {
    var stress = 0, seen = {};
    sorted(moment.k).forEach(function (frame) {
      var at = frame.at, key = frameKey(frame);
      if (Object.prototype.hasOwnProperty.call(seen, at) && seen[at] !== key) stress++;
      seen[at] = key;
    });
    return stress < STRESS_LIMIT ? Math.max(0, 1 - stress / STRESS_LIMIT) : 0;
  }
  function components(moment) {
    var frames = expand(moment), generation = sorted(moment.k).length, path = 0, jerk = 0;
    for (var i = 1; i < frames.length; i++) {
      path += Math.hypot(frames[i].x - frames[i - 1].x, frames[i].z - frames[i - 1].z);
    }
    for (var j = 2; j < frames.length; j++) {
      jerk += Math.abs(frames[j].s - 2 * frames[j - 1].s + frames[j - 2].s);
    }
    var glow = mean(frames.map(function (frame) { return frame.g; }));
    var spike = mean(frames.map(function (frame) { return frame.p; }));
    var variance = mean(LIN.map(function (field) {
      return std(frames.map(function (frame) { return frame[field]; }));
    }));
    return {
      generation: generation,
      articulation: Math.min(generation / 8, 1),
      motion: Math.min(path / 5, 1),
      jerk: Math.min(jerk / 2, 1),
      glow: glow,
      spike: spike,
      variance: Math.min(variance * 3, 1),
      vitality: vitality(moment)
    };
  }
  function componentsV2(moment) {
    var base = components(moment), frames = expand(moment), keyframes = sorted(moment.k), effective = 1;
    for (var i = 1; i < keyframes.length; i++) {
      if (frameKey(keyframes[i]) !== frameKey(keyframes[i - 1])) effective++;
    }
    function clipped(frame) {
      var count = LIN.filter(function (field) { return frame[field] <= 0.01 || frame[field] >= 0.99; }).length;
      count += DRIFT.filter(function (field) { return Math.abs(frame[field]) >= 0.99; }).length;
      return count / (LIN.length + DRIFT.length);
    }
    var clipping = Math.max(mean(frames.map(clipped)), mean(keyframes.map(clipped)));
    return Object.assign({}, base, {
      effective_articulation: Math.min(effective / 8, 1),
      glow_balance: Math.max(0, 1 - Math.abs(base.glow - 0.62) / 0.62),
      spike_balance: Math.max(0, 1 - Math.abs(base.spike - 0.42) / 0.58),
      smoothness: Math.max(0, 1 - base.jerk),
      clipping_penalty: Math.min(clipping * 0.55, 0.55)
    });
  }
  function strength(moment, version) {
    var v2 = version === "v2" || version === "double-jump-strength/2.0";
    var c = v2 ? componentsV2(moment) : components(moment), raw;
    if (v2) {
      var axes = [c.effective_articulation, c.motion, c.glow_balance, c.spike_balance, c.variance];
      raw = 0.24 * axes[0] + 0.24 * axes[1] + 0.16 * axes[2] + 0.12 * axes[3] +
        0.14 * axes[4] + 0.10 * c.smoothness;
      raw = raw * (0.75 + 0.25 * Math.min.apply(Math, axes)) - c.clipping_penalty;
    } else {
      raw = 0.30 * c.articulation + 0.25 * c.motion + 0.10 * c.jerk +
        0.15 * c.glow + 0.08 * c.spike + 0.12 * c.variance;
    }
    return +Math.max(0, Math.min(1, c.vitality * raw)).toFixed(4);
  }
  return { components: components, componentsV2: componentsV2, strength: strength, vitality: vitality };
});
