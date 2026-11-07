/* Slate-scoped Trends filters. Pure functions, no DOM.
   Embedded by build_html.py. Also runnable under node (module.exports). */
(function (root, factory) {
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root) root.HWTrends = api;
})(typeof window !== 'undefined' ? window : null, function () {
  var FLOOR = { PTS: 0.5, REB: 0.5, AST: 0.4, FG3M: 0.2 };
  var COUNT = ['PTS', 'REB', 'AST', 'FG3M'];
  var ROLE = { 'Usage spike': 1, 'Usage drop': 1, 'Role change': 1, 'Team change': 1 };
  var STAT_NAME = { PTS: 'Points', REB: 'Rebounds', AST: 'Assists', FG3M: '3-pointers' };
  var UP = { 'Hot streak': 1, 'Role change': 1, 'Usage spike': 1, 'Change point': 1, 'Injury usage bump': 1, 'Hot from 3': 1, '3P% regression': 1 };

  function gid(x) { return x == null ? '' : String(x); }

  function slateIndex(games, day) {
    var gs = (games || []).filter(function (g) { return g.date === day; });
    var byPid = {};
    gs.forEach(function (g) {
      ['home', 'away'].forEach(function (side) {
        var team = g[side];
        var opp = g[side === 'home' ? 'away' : 'home'];
        var players = (g.teams[side].players) || [];
        players.forEach(function (e) {
          byPid[e.id] = { pid: e.id, team: team, opp: opp, side: side, gid: gid(g.id), home: g.home, away: g.away, inj: e.inj_delta || null };
        });
      });
    });
    return { games: gs, byPid: byPid };
  }

  function reconcile(idx, gameId, team) {
    gameId = gid(gameId) || 'all';
    team = team || 'all';
    var ids = {};
    var teams = {};
    idx.games.forEach(function (g) { ids[gid(g.id)] = 1; teams[g.home] = 1; teams[g.away] = 1; });
    if (gameId !== 'all' && !ids[gameId]) gameId = 'all';
    if (team !== 'all' && !teams[team]) team = 'all';
    if (gameId !== 'all' && team !== 'all') {
      var g = idx.games.filter(function (x) { return gid(x.id) === gameId; })[0];
      if (!g || (team !== g.home && team !== g.away)) team = 'all';
    }
    return { gameId: gameId, team: team };
  }

  function matchupChoices(idx, team) {
    return idx.games.filter(function (g) { return team === 'all' || g.home === team || g.away === team; });
  }

  function teamChoices(idx, gameId) {
    if (gameId && gameId !== 'all') {
      var g = idx.games.filter(function (x) { return gid(x.id) === gid(gameId); })[0];
      return g ? [g.away, g.home] : [];
    }
    var t = [];
    idx.games.forEach(function (g) {
      if (t.indexOf(g.away) < 0) t.push(g.away);
      if (t.indexOf(g.home) < 0) t.push(g.home);
    });
    return t;
  }

  function parseDeltas(text) {
    var out = {};
    var re = /\b(PTS|REB|AST|3PM)\s*([+-]?\d+(?:\.\d+)?)/g, m;
    while ((m = re.exec(text || ''))) out[m[1] === '3PM' ? 'FG3M' : m[1]] = parseFloat(m[2]);
    return out;
  }

  function injuryMoves(trend, loc) {
    var d = {};
    if (loc && loc.inj && loc.inj.length >= 4) {
      COUNT.forEach(function (s, i) { if (loc.inj[i] != null && isFinite(+loc.inj[i])) d[s] = +loc.inj[i]; });
    } else d = parseDeltas(trend.text);
    return COUNT.filter(function (s) { return d[s] != null && Math.abs(d[s]) >= FLOOR[s]; }).map(function (s) { return { stat: s, value: d[s] }; });
  }

  function inScope(trend, idx, gameId, team) {
    var loc = idx.byPid[trend.pid];
    if (!loc) return false;
    if (gameId !== 'all' && loc.gid !== gid(gameId)) return false;
    if (team !== 'all' && loc.team !== team) return false;
    if (trend.game != null && gid(trend.game) !== loc.gid) return false;
    return true;
  }

  function isUp(trend) {
    return trend.dir > 0 && UP[trend.type] && trend.type !== 'Matchup edge' && trend.type !== 'Positional matchup';
  }

  function matchesStat(trend, stat, loc) {
    if (trend.type === 'Injury usage bump') return injuryMoves(trend, loc).length > 0 && (stat === 'ALL' || injuryMoves(trend, loc).some(function (m) { return m.stat === stat; }));
    if (ROLE[trend.type]) return stat === 'ALL';
    if (stat === 'ALL') return true;
    return trend.stat === stat;
  }

  function figures(trend, stat, loc) {
    if (trend.type === 'Injury usage bump') {
      var moves = injuryMoves(trend, loc);
      var show = stat === 'ALL' ? moves : moves.filter(function (m) { return m.stat === stat; });
      return { kind: 'deltas', parts: show };
    }
    if (trend.lv) return { kind: 'level', stat: trend.stat, now: trend.lv[1], before: trend.lv[0] };
    if (trend.pct) return { kind: 'pct', stat: trend.stat, now: trend.pct[0], before: trend.pct[1] };
    var by = /by\s*([+-]?\d+(?:\.\d+)?)/.exec(trend.text || '');
    if (by) return { kind: 'delta', stat: trend.stat, value: parseFloat(by[1]) };
    var pct = /(\d+(?:\.\d+)?)%\s*(above|below)/.exec(trend.text || '');
    if (pct) return { kind: 'rel', stat: trend.stat, value: parseFloat(pct[1]) * (pct[2] === 'below' ? -1 : 1) };
    if (trend.z != null) return { kind: 'z', stat: trend.stat, value: trend.z };
    return { kind: 'none', stat: trend.stat };
  }

  function detailLine(trend, stat, loc) {
    if (trend.type !== 'Injury usage bump' || stat === 'ALL') return trend.text || '';
    var m = injuryMoves(trend, loc).filter(function (x) { return x.stat === stat; })[0];
    if (!m) return '';
    var name = STAT_NAME[stat] || stat;
    return 'Projection ' + (m.value > 0 ? '+' : '') + m.value.toFixed(1) + ' ' + name + ' with teammates out.';
  }

  function apply(D, state) {
    state = state || {};
    var idx = slateIndex(D.games, state.day);
    var rec = reconcile(idx, state.gameId || 'all', state.team || 'all');
    var stat = state.stat || 'ALL';
    var type = state.type || 'All';
    function locOf(t) { return idx.byPid[t.pid]; }
    var pool = (D.trends || []).filter(function (t) {
      return inScope(t, idx, rec.gameId, rec.team) && matchesStat(t, stat, locOf(t));
    });
    var counts = { All: pool.length };
    var upPids = {};
    pool.forEach(function (t) {
      counts[t.type] = (counts[t.type] || 0) + 1;
      if (isUp(t)) upPids[t.pid] = 1;
    });
    counts['▲ Trending Up'] = Object.keys(upPids).length;
    if (type !== 'All' && !counts[type]) type = 'All';
    var rows;
    if (type === '▲ Trending Up') {
      var best = {};
      pool.filter(isUp).forEach(function (t) {
        if (!best[t.pid] || t.score > best[t.pid].score) best[t.pid] = t;
      });
      rows = Object.keys(best).map(function (k) { return best[k]; });
    } else if (type === 'All') rows = pool.slice();
    else rows = pool.filter(function (t) { return t.type === type; });
    rows.sort(function (a, b) { return b.score - a.score; });
    rows = rows.map(function (t) {
      var loc = locOf(t);
      return Object.assign({}, t, { _loc: loc, _fig: figures(t, stat, loc), _detail: detailLine(t, stat, loc) });
    });
    return {
      gameId: rec.gameId, team: rec.team, stat: stat, type: type, rows: rows, counts: counts,
      matchups: matchupChoices(idx, rec.team), teams: teamChoices(idx, rec.gameId), nGames: idx.games.length
    };
  }

  return {
    FLOOR: FLOOR, STAT_NAME: STAT_NAME, slateIndex: slateIndex, reconcile: reconcile,
    matchupChoices: matchupChoices, teamChoices: teamChoices, injuryMoves: injuryMoves,
    inScope: inScope, matchesStat: matchesStat, figures: figures, detailLine: detailLine, apply: apply
  };
});
