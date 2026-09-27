#!/usr/bin/env python3
import importlib.util, pathlib, unittest
P=pathlib.Path(__file__).parents[1]/"scripts"/"auto_publish_windsor.py"
spec=importlib.util.spec_from_file_location("publisher",P); m=importlib.util.module_from_spec(spec)
import os; os.environ.setdefault("INSTAGRAM_ACCOUNT_ID","test"); spec.loader.exec_module(m)
class EligibilityTests(unittest.TestCase):
 def base(self):
  n={"category":"CIÊNCIA","title":"NASA retoma instrumento","summary":"Observatório voltou a operar","body":[]}
  i={"state":"FEED_PENDENTE","portal":True,"feed_art":True,"feed_media_id":None,"art_sha256":"abc","art_validation":{"passed":True}}
  p={"passed":True,"expected_sha256":"abc","public_sha256":"abc"}
  return n,i,p
 def test_valid_item(self):
  n,i,p=self.base(); self.assertTrue(m.eligible_item("x",i,n,p))
 def test_existing_media_is_blocked(self):
  n,i,p=self.base(); i["feed_media_id"]="123"; self.assertFalse(m.eligible_item("x",i,n,p))
 def test_sha_mismatch_is_blocked(self):
  n,i,p=self.base(); p["public_sha256"]="bad"; self.assertFalse(m.eligible_item("x",i,n,p))
 def test_failed_validation_is_blocked(self):
  n,i,p=self.base(); i["art_validation"]["passed"]=False; self.assertFalse(m.eligible_item("x",i,n,p))
 def test_politics_is_blocked(self):
  n,i,p=self.base(); n["title"]="Ministro fala no Congresso"; self.assertFalse(m.eligible_item("x",i,n,p))
 def test_electoral_is_blocked(self):
  n,i,p=self.base(); n["summary"]="Decisão do TSE sobre processo eleitoral"; self.assertFalse(m.eligible_item("x",i,n,p))
if __name__=="__main__": unittest.main()
