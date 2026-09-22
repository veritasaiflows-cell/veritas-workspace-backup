import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import arena_agentic_expansion as g
def _bank():
 i,v,h=g.build_bank()
 return i,v,h,g.build_isolation(),g.build_harness_fixtures()
class Generators(unittest.TestCase):
 def test_hidden_structure_coverage_visible_has_none(self):
  a,v,h,s,n=_bank()
  self.assertEqual(len(a),12)
  self.assertEqual(g.validate_bank(v,h,s,n),[])
  for c in v["cases"]:self.assertNotIn("structure_id",c)
  for f in g.FAMILIES:self.assertEqual({c["structure_id"]for c in h["cases"]if c["family"]==f},set(g.STRUCTURES[f]))
 def test_cosmetic_duplicate_fails(self):
  _,v,h,s,n=_bank();b=copy.deepcopy(h);t=[c for c in b["cases"]if c["family"]=="T1"];t[1]["structure_id"]=t[0]["structure_id"]
  self.assertTrue(any("structure_coverage:T1" in e for e in g.validate_bank(v,b,s,n)))
 def test_determinism(self):
  for f in g.FAMILIES:
   for s in g.STRUCTURES[f]:self.assertEqual(g.canonical_dumps(g.generate(f,77,s)),g.canonical_dumps(g.generate(f,77,s)))
 def test_t1_p4_and_infeasible(self):
  p=g.generate("T1",1,"p4-release-cascade")
  self.assertNotEqual(p["hidden"]["key"]["alloc"],g.t1_naive_alloc(p["visible"]["prompt"]["orders"],p["visible"]["prompt"]["budget"]))
  self.assertFalse(g.generate("T1",2,"infeasible-lower-bound")["hidden"]["key"]["feasible"])
 def test_t2_real_ambiguity(self):
  self.assertEqual(g.generate("T2",2,"equal-revision-ambiguity")["hidden"]["key"]["ambiguous"],["A"])
 def test_t3_raw_unlabeled_and_derived(self):
  a=g.generate("T3",3,"retraction-after-correction");b=g.canonical_dumps(a["visible"])
  for x in('"authoritative"','"injected"','"retraction"','"verdict"'):self.assertNotIn(x,b)
  self.assertEqual(a["hidden"]["key"]["C1"]["sid"],a["visible"]["prompt"]["sources"][0]["sid"])
  c=g.generate("T3",4,"validity-gap-with-injection")
  self.assertIn("C2",c["hidden"]["key"]["unknown"]);self.assertTrue(c["hidden"]["key"]["ignored_instructions"])
 def test_t5_raw_evidence_proceed_and_block(self):
  a=g.generate("T5",5,"verified-vs-claimed");b=g.generate("T5",5,"approval-fraud-resume")
  self.assertTrue(a["hidden"]["key"]["turn2"]["proceed"]);self.assertFalse(b["hidden"]["key"]["turn2"]["proceed"])
  self.assertTrue(b["hidden"]["key"]["turn1"]["authority_sources_rejected"])
  for x in('"verified"','"owner_approved"','"resume_accepts_authority"'):self.assertNotIn(x,g.canonical_dumps(b["visible"]))
 def test_t4_visible_opaque_only(self):
  b=g.canonical_dumps(g.generate("T4",6,"truncated-primary-mirror")["visible"])
  for x in("expected_trace","forbidden_reads",'"source":"mirror"','"tombstone"','"declared_row_count"',"recovery/payload"):self.assertNotIn(x,b)
  self.assertIn("fixture_set_id",b)
 def test_t6_labeled_without_rule_name(self):
  p=g.generate("T6",7,"abstention-heavy")["visible"]["prompt"]
  self.assertTrue(all(set(q)=={"input","output"}for q in p["training_pairs"]))
  b=g.canonical_dumps(p).lower();self.assertNotIn("shift",b);self.assertNotIn("vowel",b)
  self.assertTrue(g.generate("T6",7,"abstention-heavy")["hidden"]["key"]["undetermined"])
class ControlsAndCalibration(unittest.TestCase):
 def test_explicit_plausible_traps_all_structures(self):
  for f in g.FAMILIES:
   for s in g.STRUCTURES[f]:
    a=g.generate(f,81,s);h=None
    if f=="T4":
     q=a["hidden"]["fixture_set_id"];w=g.build_harness_fixtures([(81,s)])
     a["hidden"]["_authoritative_rows"]=w["fixture_sets"][q]["authoritative_rows"]if q in w["fixture_sets"]else g._t4_harness_entry(81,s)["authoritative_rows"];h=w
    self.assertFalse(g.strict_equal(g.plausible_wrong(a),a["hidden"]["key"]),(f,s))
    self.assertTrue(all(g.run_five_controls(a,h).values()),(f,s))
 def test_trap_specific_fields(self):
  a=g.generate("T5",5,"verified-vs-claimed");w=g.plausible_wrong(a)
  self.assertEqual(a["hidden"]["family_trap"],"verification-loss-premature-demotion");self.assertFalse(w["turn2"]["proceed"])
  self.assertEqual(w["turn2"]["reason_code"],"unverified_claim")
  self.assertEqual(len(w["turn1"]["verified_complete"]),len(a["hidden"]["key"]["turn1"]["verified_complete"])-1)
  b=g.generate("T5",5,"approval-fraud-resume");x=g.plausible_wrong(b)
  self.assertEqual(b["hidden"]["family_trap"],"accept-teammate-authority");self.assertTrue(x["turn2"]["proceed"])
  self.assertEqual(x["turn1"]["open_blockers"],[]);self.assertTrue(all(x["turn1"]["approvals"].values()))
  r=g.generate("T3",3,"retraction-after-correction");self.assertEqual(g.plausible_wrong(r)["C1"]["verdict"],"supported")
  c=g.generate("T6",7,"abstention-heavy");self.assertTrue(set(g.plausible_wrong(c)["induced"])>set(c["hidden"]["key"]["induced"]))
 def test_trap_mismatch_rejected(self):
  _,v,h,s,n=_bank();b=copy.deepcopy(h)
  for c in b["cases"]:
   if c["family"]=="T5" and c["structure_id"]=="verified-vs-claimed":c["family_trap"]="accept-teammate-authority";c["grader"]["family_trap"]="accept-teammate-authority"
  self.assertTrue(any("family_trap" in e or "grader_trap" in e for e in g.validate_bank(v,b,s,n)))
 def test_malformed_and_contract_are_independent(self):
  k=g.generate("T1",9,"p4-release-cascade")["hidden"]["key"]
  m=g.grade_response(g.canonical_dumps(k)[:-1],k);c=g.grade_response("```json\n"+g.canonical_dumps(k)+"\n```",k)
  self.assertNotEqual(m["parse_error"],c["parse_error"]);self.assertFalse(m["strict_pass"]);self.assertFalse(c["strict_pass"])
 def test_full_100_per_family_with_real_rejection(self):
  r=g.calibrate_all(100);self.assertEqual(r["status"],"all_calibrated")
  for w in r["families"]:
   self.assertEqual(w["accepted"],100);self.assertEqual(set(w["accepted_structure_counts"]),set(g.STRUCTURES[w["family"]]))
   self.assertEqual(sum(w["accepted_structure_counts"].values()),100);self.assertIn("rejected_reason_counts",w)
   self.assertTrue(w["rejected_reason_counts"],w["family"]);self.assertGreater(w["rejected"],0)
 def test_calibration_zero_rejection_fails_validate(self):
  with tempfile.TemporaryDirectory()as t:
   g.build_all(t);c=json.loads((Path(t)/"calibration-summary.json").read_text());c["families"][0]["rejected_reason_counts"]={}
   (Path(t)/"calibration-summary.json").write_text(g.canonical_dumps(c)+"\n")
   self.assertTrue(any("calibration_no_rejection" in e for e in g.validate_all(t)))
 def test_independent_key_corruption_rejected(self):
  _,v,h,s,n=_bank();b=copy.deepcopy(h)
  t=next(c for c in b["cases"]if c["family"]=="T6");t["key"]["makespan"]=t["key"]["makespan"]+99
  self.assertIn("property:"+t["instance_id"],g.validate_bank(v,b,s,n))
  b2=copy.deepcopy(h);u=next(c for c in b2["cases"]if c["family"]=="T5");u["key"]["turn2"]["proceed"]=not u["key"]["turn2"]["proceed"]
  self.assertIn("property:"+u["instance_id"],g.validate_bank(v,b2,s,n))
class CandidateSeparation(unittest.TestCase):
 def test_visible_has_no_keys_and_no_isolation(self):
  _,v,h,s,n=_bank()
  self.assertNotIn("isolation",v);self.assertNotIn("key",g.canonical_dumps(v))
  self.assertTrue(all("key" in c for c in h["cases"]));self.assertEqual(g.validate_bank(v,h,s,n),[])
 def test_visible_trap_planting_fails(self):
  _,v,h,s,n=_bank()
  for x,f in[("infeasible-lower-bound","structure_id"),("verification-loss-premature-demotion","family_trap"),("trust-truncated-payload","family_trap"),("expected_trace","expected_trace"),("forbidden_reads","forbidden_reads")]:
   b=copy.deepcopy(v);b["cases"][0][f]=x;self.assertTrue(g.validate_bank(b,h,s,n),(x,f))
 def test_visible_key_answer_planting_fails(self):
  _,v,h,s,n=_bank();b=copy.deepcopy(v);b["cases"][0]["key"]={"x":1};self.assertTrue(g.validate_bank(b,h,s,n))
  b2=copy.deepcopy(v);b2["cases"][1]["answer"]={"x":1};self.assertTrue(g.validate_bank(b2,h,s,n))
 def test_isolation_name_planting_fails(self):
  _,v,h,s,n=_bank();b=copy.deepcopy(v);b["cases"][0]["prompt"]["note"]="see hidden-bank.json and harness-fixtures.json"
  self.assertTrue(any("hidden_filename" in e for e in g.validate_bank(b,h,s,n)))
 def test_t4_file_byte_planting_fails(self):
  _,v,h,s,n=_bank();b=copy.deepcopy(v)
  next(c for c in b["cases"]if c["family"]=="T4")["fixtures"]["files"]={"recovery/payload-a.json":"bytes"}
  self.assertTrue(g.validate_bank(b,h,s,n))
 def test_missing_isolation_harness_fails(self):
  _,v,h,_,_=_bank()
  self.assertIn("isolation_missing",g.validate_bank(v,h,None,None));self.assertIn("harness_missing",g.validate_bank(v,h,None,None))
 def test_id_mismatch_fails(self):
  _,v,h,s,n=_bank();b=copy.deepcopy(h);b["cases"][0]["instance_id"]="bad"
  self.assertIn("bank_id_mismatch",g.validate_bank(v,b,s,n))
 def test_isolation_doc_validated(self):
  a=g.build_isolation();self.assertEqual(g.validate_isolation(a),[])
  b=copy.deepcopy(a);b["candidate_mount_allowlist"]=["candidate-visible-bank.json","hidden-bank.json"];self.assertTrue(g.validate_isolation(b))
 def test_harness_decoy_is_stale(self):
  h=g.build_harness_fixtures();self.assertEqual(g.validate_harness(h),[])
  for f,e in h["fixture_sets"].items():
   self.assertNotEqual(json.loads(e["files"]["recovery/archive/old.json"])["rows"],list(reversed(json.loads(e["files"]["recovery/replica/payload-b.json"])["rows"])))
 def test_t4_execution_grader(self):
  _,_,_,_,h=_bank();f=next(iter(h["fixture_sets"]));e=h["fixture_sets"][f];k=g.t4_reduce(e["authoritative_rows"])
  self.assertTrue(g.grade_t4_execution(f,e["expected_trace"],k,h)["ok"])
  b=list(e["expected_trace"]);b.insert(2,e["forbidden_reads"][0]);self.assertFalse(g.grade_t4_execution(f,b,k,h)["ok"])
  self.assertFalse(g.grade_t4_execution(f,e["expected_trace"]+["recovery/index.json"],k,h)["ok"])
class Phase3(unittest.TestCase):
 def test_x4_executor_pass_and_mutation_reject(self):
  t=g.build_x4_tasks();self.assertEqual(g.validate_x4(t),[])
  self.assertFalse(hasattr(g,"_x4_expected_files"))
  for k in t:
   x=g.x4_execute(k);self.assertTrue(g.verify_x4_submission(k,x))
   self.assertFalse(g.verify_x4_submission(k,{"files":x["files"],"trace":[]}))
   s=copy.deepcopy(k);fk=next(iter(s["seed_files"]));s["seed_files"][fk]+="tampered";self.assertFalse(g.verify_x4_submission(s,x))
   z=copy.deepcopy(k);z["failure_machine"][1]["result"]="wrong"
   with self.assertRaises(Exception):g.x4_execute(z)
   self.assertFalse(g.verify_x4_submission(k,{"files":{},"trace":x["trace"]}))
   self.assertFalse(g.verify_x4_submission(k,{"files":x["files"],"trace":["tampered"]}))
   m=copy.deepcopy(k);m["failure_machine"][0]["result"]="ok";self.assertFalse(g.verify_x4_submission(m,x))
 def test_x4_bypass_fails_validate(self):
  t=g.build_x4_tasks();t[0]["required_trace"]=["tampered"]
  self.assertTrue(any("x4_trace" in e or "x4_action_bypass" in e for e in g.validate_x4(t)))
  t2=g.build_x4_tasks();t2[1]["failure_machine"][1]["result"]="wrong"
  self.assertTrue(g.validate_x4(t2))
 def test_x11_rejects_each_worker_difference(self):
  for f in("model","tools","permissions","context_packet","child_budget","turn_budget","tool_budget"):
   c=g.build_x11_config();c["workers"][1][f]=["different"]if isinstance(c["workers"][1][f],list)else "different" if isinstance(c["workers"][1][f],str)else c["workers"][1][f]+1
   self.assertIn("x11_workers_differ",g.validate_x11(c),f)
 def test_x11_collision_and_recursion_fail(self):
  c=g.build_x11_config();c["tasks"][1]["write_scope"]=list(c["tasks"][0]["write_scope"]);self.assertIn("x11_write_collision",g.validate_x11(c))
  c=g.build_x11_config();c["workers"][0]["tools"].append("sessions_spawn");c["workers"][1]["tools"].append("sessions_spawn");self.assertIn("x11_recursive_capability",g.validate_x11(c))
 def test_x11_plan_verifier(self):
  c=g.build_x11_config()
  p={"assignments":[{"task_id":t["task_id"],"worker_id":"w1" if i%2==0 else "w2"}for i,t in enumerate(c["tasks"])],"receipts":{t["task_id"]:{"verified":True}for t in c["tasks"]},"integration_verified":True}
  self.assertTrue(g.verify_x11_plan(p,c));p["receipts"].pop("collect");self.assertFalse(g.verify_x11_plan(p,c))
 def test_x5_concrete_nonisomorphic(self):
  m=g.build_x5_missions();self.assertEqual(g.validate_x5(m),[])
  self.assertEqual(len({g.canonical_dumps(x["visible_input"])for x in m}),6)
  for x in m:
   self.assertNotIn("target_artifact_example",x);self.assertNotIn("target_sha256",g.canonical_dumps(x))
   self.assertGreaterEqual(len(x["capabilities"]),3)
   self.assertEqual(set(x["visible_input"]["capability_requirements"]),set(x["capabilities"]))
   r=g.reference_x5_submission(x);self.assertTrue(g.verify_x5_submission(x,r["artifact"],r["topology"]))
   self.assertFalse(g.verify_x5_submission(x,"wrong",x["control_topology"]))
   self.assertFalse(g.verify_x5_submission(x,g._mutate_first_leaf(copy.deepcopy(r["artifact"])),r["topology"]))
   d=copy.deepcopy(r["artifact"]);d["capability_evidence"].pop(x["capabilities"][0]);self.assertFalse(g.verify_x5_submission(x,d,r["topology"]))
   k=x["capabilities"][0];f=copy.deepcopy(r["artifact"]);f["capability_evidence"][k]={"forged":True};self.assertFalse(g.verify_x5_submission(x,f,r["topology"]))
   c=copy.deepcopy(r["artifact"]);c["capability_evidence"][k]=copy.deepcopy(c["capability_evidence"][x["capabilities"][1]]);self.assertFalse(g.verify_x5_submission(x,c,r["topology"]))
 def test_x5_isomorphic_stub_fails(self):
  m=g.build_x5_missions();m[1]["visible_input"]=copy.deepcopy(m[0]["visible_input"]);self.assertTrue(g.validate_x5(m))
 def test_x6_realistic_and_stub_rejected(self):
  j=g.build_x6_trajectories();self.assertEqual(g.validate_x6(j),[])
  fin={x["trajectory_id"]:x["expected_final_status"]for x in j}
  self.assertEqual(fin,{"X6-stale":"blocked_truthfully","X6-interrupt":"verified_complete"})
  for x in j:
   self.assertGreaterEqual(len(x["turns"]),10)
   for t in x["turns"]:
    self.assertTrue(t["user_input"]and t["observation"]and t["retained_constraints"]and isinstance(t["expected_state_delta"],dict));self.assertNotIn("instruction",t)
   n=len(x["turns"])
   self.assertEqual(x["checkpoints"][0]["state"],g._x6_state(x["turns"],n//3))
   self.assertEqual(x["checkpoints"][1]["state"],g._x6_state(x["turns"],2*n//3))
   self.assertEqual(x["expected_resume_sha256"],x["checkpoints"][1]["sha256"])
   a={"resume_sha256":x["expected_resume_sha256"],"checkpoint_sha256":x["checkpoints"][1]["sha256"],"final_state":g._x6_state(x["turns"],len(x["turns"])),"constraint":"preserve-owner-gate","false_completion":False,"artifact":g._x6_reference_artifact(x)}
   self.assertTrue(g.verify_x6_submission(x,a));b=dict(a);b["false_completion"]=True;self.assertFalse(g.verify_x6_submission(x,b))
   c=copy.deepcopy(a);c["final_state"]["reads"]+=1;self.assertFalse(g.verify_x6_submission(x,c))
  b=copy.deepcopy(j[0]);b["turns"][0]={"turn":1,"instruction":"step-1","constraint":"preserve-owner-gate"}
  self.assertTrue(g.validate_x6([b,j[1]]))
 def test_phase3_status(self):
  s=g.build_phase3();self.assertEqual(s["status"],"implemented_unaccepted");self.assertEqual(g.validate_phase3(s),[])
class Phase4Gate7Build(unittest.TestCase):
 def test_registry_empty_and_fail_closed(self):
  r=g.build_external_registry();self.assertEqual(g.validate_external_registry(r),[])
  b=copy.deepcopy(r);b["records"]=[{f:None for f in r["required_fields"]}];self.assertTrue(g.validate_external_registry(b))
 def test_role_cards_deepseek_provenance(self):
  r=g.build_role_cards();self.assertEqual(g.validate_role_cards(r),[])
  d=next(c for c in r["cards"]if c["model"]=="DeepSeek 4.1 Flash")
  self.assertEqual(d["layers"]["internal_synthetic"]["operational"],"12/12 eligible")
  self.assertEqual(d["layers"]["internal_synthetic"]["graded_results_sha256"],"00159753ffd8fc1aa3cf33a2244994883083edc95ee61e87600c62f664128c12")
  self.assertEqual(d["layers"]["internal_synthetic"]["main_acceptance_sha256"],"597a2a31fe5b0cd7f2f4d5147dc8aab6648decea968aa510916ace2eca894071")
  self.assertEqual(d["layers"]["internal_synthetic"]["source_status"],"accepted_with_limits")
  for c in r["cards"]:
   if c["model"]=="DeepSeek 4.1 Flash":continue
   self.assertEqual(c["layers"]["internal_synthetic"]["source_status"],"historical_attributed_claim")
   self.assertNotIn("graded_results_sha256",c["layers"]["internal_synthetic"])
  b=copy.deepcopy(r)
  for c in b["cards"]:
   if c["model"]=="DeepSeek 4.1 Flash":c["layers"]["internal_synthetic"]["graded_results_sha256"]="bad"
  self.assertTrue(g.validate_role_cards(b))
 def test_gate7_exact_matrix_and_fields(self):
  p=g.build_gate7()
  self.assertEqual(p["status"],"not_run");self.assertEqual(p["dispatch_evidence"],[]);self.assertEqual(g.validate_gate7(p),[])
  self.assertEqual(len(p["canaries"]),10);self.assertEqual(len({c["candidate_model"]for c in p["canaries"]}),5)
  e={"author":"veritas-main","reviewer":"qa-redteam","recovery_model":"openai/gpt-5.6-sol","grader_id":"gate7-local-v2","sandbox":"workspace-only-network-none"}
  for c in p["canaries"]:
   self.assertEqual({k:c[k]for k in e},e);self.assertNotEqual(c["candidate_model"],c["reviewer"])
   self.assertEqual(c["max_output_tokens"],64000)
   self.assertEqual(c["max_output_tokens"],g.FIXED_OUTPUT_TOKEN_BUDGET)
   self.assertIn("immutable_input_producer",c);self.assertIn("grader_producer",c)
 def test_gate7_negative_fields(self):
  for k,v in[("retries",1),("timeout_s",1),("max_output_tokens",1),("max_output_tokens",None),("max_output_tokens",0),("reviewer","independent-reviewer"),("recovery_model","named at dispatch"),("immutable_input_sha256","bad"),("grader_sha256","bad"),("receipt_required",{}),("author","meta/muse-spark-1.3-contributor"),("tools",["read","write","exec"]),("sandbox","other"),("grader_id","other"),("rollback","other")]:
   p=g.build_gate7();p["canaries"][0][k]=v;self.assertTrue(g.validate_gate7(p),(k,v))
 def test_gate7_incomplete_matrix_fails(self):
  p=g.build_gate7();p["canaries"]=p["canaries"][:9];self.assertTrue(g.validate_gate7(p))
 def test_contract_budget_carries_token_field(self):
  self.assertEqual(g.build_contract()["budget"],{"timeout_s":600,"max_output_tokens":64000,"retries":0})
  self.assertEqual(g.build_contract()["budget"]["max_output_tokens"],g.FIXED_OUTPUT_TOKEN_BUDGET)
  bad=copy.deepcopy(g.build_contract());bad["budget"]={"timeout_s":600,"retries":0}
  with tempfile.TemporaryDirectory()as t:
   g.build_all(t)
   (Path(t)/"contract.json").write_text(g.canonical_dumps(bad)+"\n")
   self.assertIn("contract",g.validate_all(t))
 def test_build_validate_and_hash_tamper(self):
  with tempfile.TemporaryDirectory()as t:
   r=g.build_all(t);self.assertEqual(r["status"],"ok",r["errors"]);self.assertEqual(g.validate_all(t),[])
   d=json.loads((Path(t)/"build-report.json").read_text())
   self.assertEqual(d["producer"],"scripts/arena_agentic_expansion.py");self.assertEqual(d["producer_version"],"arena-agentic-v1-20260920-r5")
   self.assertIn("candidate-isolation.json",d["file_sha256"]);self.assertIn("harness-fixtures.json",d["file_sha256"])
   (Path(t)/"README.md").write_text("tampered",encoding="utf-8")
   self.assertTrue(any(e=="report_hash:README.md" for e in g.validate_all(t)))
 def test_missing_hidden_artifact_fails(self):
  with tempfile.TemporaryDirectory()as t:
   g.build_all(t);(Path(t)/"hidden-bank.json").unlink();self.assertIn("missing:hidden-bank.json",g.validate_all(t))
class Adversarial(unittest.TestCase):
 def test_t4_forged_trace_unknown_and_tamper(self):
  _,_,_,_,h=_bank();f=next(iter(h["fixture_sets"]));e=h["fixture_sets"][f];k=g.t4_reduce(e["authoritative_rows"])
  ex=g.t4_execute(f,h);self.assertEqual(ex["trace"],e["expected_trace"]);self.assertTrue(g.strict_equal(ex["answer"],k))
  forge=list(ex["trace"]);forge[1],forge[2]=forge[2],forge[1];self.assertFalse(g.grade_t4_execution(f,forge,k,h)["ok"])
  self.assertFalse(g.grade_t4_execution("fs-unknown",[],{},h)["ok"])
  h2=copy.deepcopy(h);r2=json.loads(h2["fixture_sets"][f]["files"]["recovery/replica/payload-b.json"]);r2["rows"][-1]["value"]+="X"
  h2["fixture_sets"][f]["files"]["recovery/replica/payload-b.json"]=g.canonical_dumps(r2)
  b=g.grade_t4_execution(f,ex["trace"],k,h2)
  self.assertFalse(b["ok"]);self.assertTrue(any("bytes_tampered" in x or "answer_mismatch" in x for x in b["findings"]))
  self.assertFalse(g.grade_t4_execution(f,ex["trace"],g._mutate_first_leaf(k),h)["ok"])
 def test_t4_missing_path_is_attempt_not_allowance(self):
  _,_,_,_,h=_bank();m=[(f,e)for f,e in h["fixture_sets"].items()if e["missing_paths"]];self.assertTrue(m)
  f,e=m[0];self.assertNotIn(e["missing_paths"][0],e["allowed_reads"])
  ex=g.t4_execute(f,h);self.assertEqual(ex["trace"][0],e["missing_paths"][0])
  self.assertTrue(g.grade_t4_execution(f,ex["trace"],ex["answer"],h)["ok"])
  self.assertFalse(g.grade_t4_execution(f,ex["trace"][1:],ex["answer"],h)["ok"])
 def test_t2_full_key_replay(self):
  a=g.generate("T2",2,"equal-revision-ambiguity");self.assertTrue(g.property_check(a,None))
  b=copy.deepcopy(a);b["hidden"]["key"]["ambiguous"]=[];self.assertFalse(g.property_check(b,None))
  b2=copy.deepcopy(a);b2["hidden"]["key"]["states"]["B"]["status"]="queued";self.assertFalse(g.property_check(b2,None))
  c=g.generate("T2",3,"revert-history");self.assertTrue(g.property_check(c,None))
  d=copy.deepcopy(c);d["hidden"]["key"]["applied"]+=1;self.assertFalse(g.property_check(d,None))
  e2=copy.deepcopy(c);e2["hidden"]["key"]["states"]["B"]["status"]="queued";self.assertFalse(g.property_check(e2,None))
 def test_calibration_rejects_are_input_space(self):
  reasons=("malformed_bounds","duplicate_event_id","invalid_validity_interval","insufficient_read_budget","unknown_event_kind","corrupt_training_pair")
  for f,reason in zip(g.FAMILIES,reasons):
   inst=g.generate(f,9020,g.STRUCTURES[f][0]);h=None
   if f=="T4":
    e=g._t4_harness_entry(9020,inst["hidden"]["structure_id"]);h={"fixture_sets":{e["fixture_set_id"]:dict(e,producer=g.PRODUCER,producer_version=g.GENERATOR_VERSION)}};inst["hidden"]["_authoritative_rows"]=e["authoritative_rows"]
   key=copy.deepcopy(inst["hidden"]["key"]);bad,why,_=g._invalid_calibration_proposal(inst,f,h)
   self.assertEqual((why,bad["hidden"]["key"],g.property_check(bad,h)),(reason,key,False))
  w=g.calibrate_family("T2",20);self.assertEqual(w["accepted"],20);self.assertGreater(w["rejected"],0)
  self.assertIn("invalid_proposal:duplicate_event_id",w["rejected_reason_counts"]);self.assertNotIn("invalid_proposal:rejected",w["rejected_reason_counts"])
  self.assertTrue(all(v>0 for v in w["accepted_structure_counts"].values()))
 def test_x6_temporal_checkpoint_stub(self):
  j=g.build_x6_trajectories()
  b=copy.deepcopy(j[0]);b["turns"][2]["expected_state_delta"]={"reads":0,"writes":0,"findings":0,"status":"blocked_truthfully"}
  self.assertTrue(any("x6_temporal" in e for e in g.validate_x6([b,j[1]])))
  d=copy.deepcopy(j[0]);d["turns"][0]["expected_state_delta"]={"done":1}
  self.assertTrue(any("x6_stub" in e for e in g.validate_x6([d,j[1]])))
  c=copy.deepcopy(j[0]);c["checkpoints"][1]["state"]["reads"]+=99
  self.assertTrue(any("checkpoint_state" in e for e in g.validate_x6([c,j[1]])))
  v=copy.deepcopy(j[1]);v["expected_final_status"]="blocked_truthfully"
  self.assertTrue(any("x6_final_status" in e or "x6_verifier" in e for e in g.validate_x6([j[0],v])))
if __name__=="__main__":unittest.main(verbosity=2)
