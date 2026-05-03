// ── Table sort ────────────────────────────────────────────────────────────────

let sortState = {};
function sortTable(tbodyId, colIndex) {
  const tbody = $(tbodyId);
  if (!tbody) return;
  const rows = Array.from(tbody.querySelectorAll('tr'));
  const key = `${tbodyId}_${colIndex}`;
  const asc = sortState[key] === undefined ? true : !sortState[key];
  sortState[key] = asc;
  rows.sort((a, b) => {
    const av = a.cells[colIndex]?.textContent.trim() || '';
    const bv = b.cells[colIndex]?.textContent.trim() || '';
    const an = parseFloat(av.replace(/[^0-9.\-]/g, ''));
    const bn = parseFloat(bv.replace(/[^0-9.\-]/g, ''));
    if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
    return asc ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  rows.forEach(r => tbody.appendChild(r));

  // Visual sort indicator — clear other columns in the same table, mark this one
  const table = tbody.closest('table');
  if (table) {
    table.querySelectorAll('th').forEach(th => {
      th.classList.remove('sorted-asc', 'sorted-desc');
    });
    const headers = table.querySelectorAll('thead th');
    if (headers[colIndex]) {
      headers[colIndex].classList.add(asc ? 'sorted-asc' : 'sorted-desc');
    }
  }
}
