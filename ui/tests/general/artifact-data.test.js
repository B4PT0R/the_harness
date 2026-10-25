import test from 'node:test';
import assert from 'node:assert/strict';
import { tableCSV, tableView, chartScale } from '../../src/artifact-data.js';

test('CSV preserves scalars and quotes while neutralizing spreadsheet formula strings', () => {
  assert.equal(tableCSV(['A'], [['=1+1'], [-2], [false], [null], ['a"b'], [' @SUM(A1)']]),
    '\uFEFF"A"\r\n"\'=1+1"\r\n"-2"\r\n"false"\r\n""\r\n"a""b"\r\n"\' @SUM(A1)"');
});
test('table filters and sorts without changing canonical rows', () => {
  const rows = [['B', 20], ['a', 3], ['A', 1]];
  assert.deepEqual(tableView(rows, 'a', {column: 1, descending: false}), [['A', 1], ['a', 3]]);
  assert.deepEqual(tableView(rows, '', {column: 1, descending: true}), [['B', 20], ['a', 3], ['A', 1]]);
  assert.equal(rows[0][0], 'B');
});
test('chart coordinates stay finite for zero, negatives and extreme finite numbers', () => {
  for (const values of [[0, 0], [-4, -1], [-10, 15], [-1e308, 1e308], [5e-324]]) {
    const {y, ticks} = chartScale([{values}]);
    for (const value of [...values, ...ticks, 0]) {
      assert.ok(Number.isFinite(y(value)));
      assert.ok(y(value) >= 19 && y(value) <= 221);
    }
  }
});
