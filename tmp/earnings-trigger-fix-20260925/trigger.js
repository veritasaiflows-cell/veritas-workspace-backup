const command = '"C:\\Users\\Veritas\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" -c "import json,pathlib; p=pathlib.Path(r\'C:\\Users\\Veritas\\.openclaw\\workspace\\tmp\\phase3-main-only-20260905\\g9-reconciliation-register-20260916.json\'); d=json.loads(p.read_text(encoding=\'utf-8\')); s=str(d.get(\'gate_state\',{}).get(\'G8\',{}).get(\'status\',\'\')).upper(); print(json.dumps({\'status\':s,\'closed\':s in {\'CLOSED\',\'PASS\',\'PASSED\',\'ACCEPTED\',\'COMPLETE\',\'COMPLETED\'}}))"';
let raw = '';
try {
  const result = await exec({command});
  raw = (result && typeof result === 'object') ? String(result.aggregated ?? '') : String(result || '');
} catch (error) {
  return {fire: false, state: {g8Status: 'READ_ERROR', held: true}};
}
let parsed = null;
try {
  const lines = String(raw).trim().split(/\r?\n/).filter(Boolean);
  parsed = JSON.parse(lines[lines.length - 1]);
} catch (error) {
  return {fire: false, state: {g8Status: 'PARSE_ERROR', held: true}};
}
if (parsed && parsed.closed === true) {
  return {fire: true, state: {g8Status: parsed.status, held: false}};
}
return {fire: false, state: {g8Status: (parsed && parsed.status) || 'UNKNOWN', held: true}};