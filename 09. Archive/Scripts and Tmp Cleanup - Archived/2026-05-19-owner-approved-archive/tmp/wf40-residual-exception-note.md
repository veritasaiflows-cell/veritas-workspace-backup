# WF40 Residual Exception Note

Timestamp: 2026-05-10 17:28 MST

Randall approved an exception to keep WF40 as residual scheduled-proof watch while WF55 remains the active workflow.

Validator implication: `workspace_governance_truth_check.py` should not emit WF40 active/next queue criticals solely because:
- active workflow is WF55, and
- next approved queue item is WF55 probability-readiness work,
provided the queue and registry explicitly document WF40 residual scheduled-proof watch.

This exception does not close WF40 and does not waive real proof failures. The next scheduled proof still must show fresh artifacts, `proof_status=ok`, `audit_stop_line=false`, and wrapper `errors=[]`.
