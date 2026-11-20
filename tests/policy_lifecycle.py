"""Hardware registry rotation test. Restores the initial policy header and firmware in finally."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import uuid
from prover.transport import Client
from prover.usb import ROOT, BINARY, generate

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--port",required=True)
    args=parser.parse_args()
    pio=Path(os.environ["USERPROFILE"])/".platformio/penv/Scripts/platformio.exe"
    directory=ROOT/"artifacts"/("policy-lifecycle-"+uuid.uuid4().hex);directory.mkdir(parents=True)
    private=ROOT/"secrets"/directory.name;private.mkdir(parents=True)
    header=ROOT/"firmware/include/policy_generated.h";original=header.read_bytes()
    (directory/"original-policy.h").write_bytes(original)
    report={"revocation_effective_only_after_device_policy_update":True}
    def native(*args):
        subprocess.run([str(BINARY),*map(str,args)],cwd=ROOT,check=True,capture_output=True)
    def flash():
        subprocess.run([str(pio),"run","--project-dir","firmware","--target","upload",
                        "--upload-port",args.port,"--silent"],cwd=ROOT,check=True)
        time.sleep(2)
    native("revoke",ROOT/"secrets/demo/registry.json",0,directory/"registry-epoch2.json")
    native("refresh",directory/"registry-epoch2.json",ROOT/"secrets/demo/credential-1.json",
           private/"credential-1-epoch2.json")
    native("policy-header",directory/"registry-epoch2.json",directory/"policy-epoch2.h")
    # A revoked member cannot obtain a new membership witness.
    failed=subprocess.run([str(BINARY),"refresh",str(directory/"registry-epoch2.json"),
        str(ROOT/"secrets/demo/credential-0.json"),str(private/"must-not-exist.json")],
        capture_output=True)
    assert failed.returncode!=0
    report["revoked_member_cannot_refresh"]=True
    # Obtain a real valid epoch-1 proof before installing epoch 2.
    client=Client(args.port)
    try:
        _,ctx,_=client.request(1)
        old_proof,old_public,_,_=generate(ROOT/"secrets/demo/credential-0.json",ctx)
    finally:client.close()
    try:
        header.write_bytes((directory/"policy-epoch2.h").read_bytes());flash()
        client=Client(args.port)
        try:
            assert client.info()["policy_epoch"]==2
            ident,_,_=client.request(1)
            denied=client.upload(ident,old_proof,old_public)
            assert denied["code"]!=0 and not denied["accepted"]
            report["old_epoch_root_proof_rejected_on_device"]=denied
            ident,ctx,_=client.request(1)
            proof,public,host,_=generate(private/"credential-1-epoch2.json",ctx)
            accepted=client.upload(ident,proof,public)
            assert accepted["code"]==0 and accepted["accepted"]==1
            report["remaining_member_refreshed_and_accepted"]=accepted
        finally:client.close()
    finally:
        header.write_bytes(original);flash()
        report["original_policy_restored"]=True
    client=Client(args.port)
    try:
        assert client.info()["policy_epoch"]==1
        ident,ctx,_=client.request(1)
        proof,public,host,_=generate(ROOT/"secrets/demo/credential-0.json",ctx)
        accepted=client.upload(ident,proof,public)
        assert accepted["accepted"]==1
        report["restored_policy_smoke_test"]=accepted
    finally:client.close()
    (ROOT/"docs/policy-lifecycle-results.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
if __name__=="__main__":main()

