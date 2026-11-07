const assert = require('assert');
const T = require('./trends_filter');

function game(id, date, away, home, players) {
  const side = (team, list) => ({ players: list.map(p => ({ id: p.id, inj_delta: p.inj || null })) });
  return { id: id, date: date, away: away, home: home, teams: { away: side(away, players.away), home: side(home, players.home) } };
}

const games = [
  game('g1', '2026-11-07', 'DEN', 'IND', {
    away: [{ id: 1, inj: [2.6, 0.1, 0.5, 0.05] }, { id: 2 }],
    home: [{ id: 3 }]
  }),
  game('g2', '2026-11-07', 'BKN', 'ATL', { away: [{ id: 4 }], home: [{ id: 5 }] }),
  game('g3', '2026-11-08', 'DEN', 'BOS', { away: [{ id: 1 }], home: [{ id: 9 }] })
];

const trends = [
  { pid: 1, type: 'Hot streak', stat: 'REB', score: 5, dir: 1, text: 'Rebounds up: 12.6 over last 5 vs 8.2', lv: [8.2, 12.6] },
  { pid: 1, type: 'Injury usage bump', stat: 'PTS', score: 4, dir: 1, game: 'g1', text: 'projection moves PTS +2.6, REB +0.1, AST +0.5 vs a full roster' },
  { pid: 1, type: 'Positional matchup', stat: 'FG3M', score: 3, dir: 1, game: 'g1', text: 'centers produce 38% above their own averages in 3PM vs IND' },
  { pid: 1, type: 'Positional matchup', stat: 'PTS', score: 2, dir: -1, game: 'g3', text: 'Next game @ BOS: guards produce 12% below' },
  { pid: 2, type: 'Role change', stat: 'MIN', score: 6, dir: 1, text: 'Minutes up: 35.6 over last 5 vs 27.4' },
  { pid: 2, type: 'Hot streak', stat: 'PTS', score: 2.2, dir: 1, text: 'Points up: 18.0 vs 12.0', lv: [12, 18] },
  { pid: 4, type: 'Team change', stat: 'PTS', score: 1, dir: 0, text: 'Joins ATL from TOR after averaging 21.5 PTS' },
  { pid: 8, type: 'Hot streak', stat: 'PTS', score: 9, dir: 1, text: 'off slate player' },
  { pid: 5, type: 'Matchup edge', stat: 'AST', score: 2, dir: 1, game: 'g2', text: 'opponent factors move projected assists by +0.55' }
];

const D = { games: games, trends: trends };

const nov7 = T.apply(D, { day: '2026-11-07', gameId: 'all', team: 'all', stat: 'ALL', type: 'All' });
assert.strictEqual(nov7.rows.some(t => t.pid === 8), false, 'off-slate player leaked');
assert.strictEqual(nov7.rows.some(t => t.game === 'g3'), false, 'Nov 8 matchup leaked onto Nov 7');
assert.ok(nov7.rows.some(t => t.pid === 1 && t.type === 'Hot streak'));
assert.deepStrictEqual(nov7.teams.slice().sort(), ['ATL', 'BKN', 'DEN', 'IND']);
assert.strictEqual(nov7.matchups.length, 2);

const reb = T.apply(D, { day: '2026-11-07', stat: 'REB' });
assert.ok(reb.rows.every(t => t.stat === 'REB' || t.type === 'Injury usage bump'));
assert.strictEqual(reb.rows.some(t => t.type === 'Injury usage bump'), false, '0.1 rebound bump shown under Rebounds');
assert.ok(reb.rows.some(t => t.type === 'Hot streak' && t.pid === 1));
assert.strictEqual(reb.rows.some(t => t.type === 'Role change'), false);
assert.strictEqual(reb.rows.some(t => t.type === 'Team change'), false);

const ast = T.apply(D, { day: '2026-11-07', stat: 'AST' });
const bump = ast.rows.find(t => t.type === 'Injury usage bump');
assert.ok(bump, 'assist bump kept');
assert.deepStrictEqual(bump._fig.parts.map(p => p.stat), ['AST']);
assert.ok(bump._detail.indexOf('Assists') >= 0);
assert.ok(bump._detail.indexOf('PTS') < 0, 'points number leaked into assists detail');
assert.ok(ast.rows.some(t => t.type === 'Matchup edge' && t.pid === 5));

const threes = T.apply(D, { day: '2026-11-07', stat: 'FG3M' });
assert.ok(threes.rows.some(t => t.type === 'Positional matchup'));
assert.strictEqual(threes.rows.some(t => t.type === 'Injury usage bump'), false, 'tiny 3PM delta shown');

const pts = T.apply(D, { day: '2026-11-07', stat: 'PTS' });
assert.ok(pts.rows.some(t => t.type === 'Injury usage bump'));
assert.strictEqual(pts.rows.some(t => t.type === 'Role change'), false);
assert.strictEqual(pts.rows.some(t => t.type === 'Team change'), false);
const allBump = T.apply(D, { day: '2026-11-07', stat: 'ALL' }).rows.find(t => t.type === 'Injury usage bump');
assert.deepStrictEqual(allBump._fig.parts.map(p => p.stat), ['PTS', 'AST']);

const denInd = T.apply(D, { day: '2026-11-07', gameId: 'g1', team: 'all', stat: 'ALL' });
assert.deepStrictEqual(denInd.teams, ['DEN', 'IND']);
assert.ok(denInd.rows.every(t => t._loc.gid === 'g1'));
assert.strictEqual(denInd.rows.some(t => t.pid === 4), false);

const teamFirst = T.apply(D, { day: '2026-11-07', gameId: 'all', team: 'DEN', stat: 'ALL' });
assert.deepStrictEqual(teamFirst.matchups.map(g => g.id), ['g1']);
assert.ok(teamFirst.rows.every(t => t._loc.team === 'DEN'));

const both = T.apply(D, { day: '2026-11-07', gameId: 'g1', team: 'BKN', stat: 'ALL' });
assert.strictEqual(both.team, 'all', 'team outside the matchup is cleared');
assert.ok(both.rows.every(t => t._loc.gid === 'g1'));

const nextDay = T.apply(D, { day: '2026-11-08', gameId: 'g1', team: 'IND', stat: 'REB' });
assert.strictEqual(nextDay.gameId, 'all');
assert.strictEqual(nextDay.team, 'all');
assert.ok(nextDay.rows.some(t => t.pid === 1 && t.type === 'Hot streak'), 'season streak follows the player onto the new slate');
assert.strictEqual(nextDay.rows.some(t => t.game === 'g1'), false, 'previous game matchup leaked');
assert.ok(nextDay.rows.some(t => t.game === 'g3' && t.stat === 'PTS') === false);

const up = T.apply(D, { day: '2026-11-07', stat: 'ALL', type: '▲ Trending Up' });
assert.ok(up.counts['▲ Trending Up'] >= 1);
assert.strictEqual(up.rows.filter(t => t.pid === 1).length, 1, 'one card per player');
assert.strictEqual(up.rows.some(t => t.type === 'Positional matchup'), false);

const upReb = T.apply(D, { day: '2026-11-07', stat: 'REB', type: '▲ Trending Up' });
assert.ok(upReb.rows.every(t => t.stat === 'REB'));

console.log('test_trends_filter: ok', nov7.rows.length, 'nov7 signals');
