"""Real hardware tests: python -m tests.device_security --port COM5 [--long]."""
import argparse
import json
from pathlib import Path
import secrets
import struct
import subprocess
import time
from prover.transport import *
from prover.usb import generate, ROOT, BINARY

def run(port, long=False):
    client = Client(port)
    records = []
    wallet = ROOT / "secrets/demo/credential-0.json"
    wallet1 = ROOT / "secrets/demo/credential-1.json"
    def record(name, action):
        started=time.perf_counter()
        value=action()
        records.append({"test":name,"passed":True,"elapsed_ms":round((time.perf_counter()-started)*1000,3),"result":value})
        print(json.dumps(records[-1]),flush=True)
    def auth(op=1,arg=0,credential=wallet):
        ident,ctx,_=client.request(op,arg)
        proof,public,host,_=generate(credential,ctx)
        response=client.upload(ident,proof,public)
        if response["code"] or not response["accepted"]:
            raise AssertionError(response)
        response["host"]=host
        return response
    def denied_upload(mutate):
        ident,ctx,_=client.request(1)
        proof,public,_,_=generate(wallet,ctx)
        proof,public=mutate(bytearray(proof),bytearray(public))
        response=client.upload(ident,proof,public)
        assert response["code"]!=0 and response["accepted"]==0 and response["maintenance"]==0,response
        return response
    def direct_denied():
        r=result(client.exchange(DIRECT,secrets.randbits(32),struct.pack("<II",3,99)))
        assert r["code"] and not r["accepted"] and not r["maintenance"]
        return r
    def positive_workflow():
        entered=auth(2,credential=wallet1);assert entered["maintenance"]==1
        changed=auth(3,42);assert changed["configuration"]==42 and changed["maintenance"]==1
        diagnostics=auth(1,credential=wallet1);assert diagnostics["configuration"]==42
        exited=auth(4,credential=wallet1);assert not exited["maintenance"]
        return [entered,changed,diagnostics,exited]
    def replay():
        ident,ctx,_=client.request(1);p,pub,_,_=generate(wallet,ctx)
        assert client.upload(ident,p,pub)["accepted"]
        r=result(client.exchange(FINISH,ident))
        assert r["code"]==3 and not r["accepted"]
        new_id,_,_=client.request(1)
        r=client.upload(new_id,p,pub)
        assert r["code"]!=0 and not r["accepted"]
        return r
    def different_operation():
        _,ctx,_=client.request(1);p,pub,_,_=generate(wallet,ctx)
        ident,_,_=client.request(2)
        r=client.upload(ident,p,pub)
        assert r["code"]!=0 and not r["accepted"] and not r["maintenance"]
        return r
    def oversized():
        ident,_,_=client.request(1)
        try:client.begin(ident,MAX_PROOF+1,b"\0"*120)
        except Denied as e:
            assert e.result["code"]==9 and not e.result["maintenance"]
            return e.result
        raise AssertionError("oversized proof accepted")
    def wrong_offset():
        ident,ctx,_=client.request(1);p,pub,_,_=generate(wallet,ctx)
        client.begin(ident,len(p),pub)
        r=result(client.exchange(CHUNK,ident,struct.pack("<I",1)+p[:64]))
        assert r["code"]==4 and not r["maintenance"]
        return r
    def interrupted():
        ident,ctx,_=client.request(1);p,pub,_,_=generate(wallet,ctx)
        client.begin(ident,len(p),pub)
        ack=client.exchange(CHUNK,ident,struct.pack("<I",0)+p[:64])
        assert struct.unpack("<II",ack)==(0,64)
        time.sleep(3.3)
        r=client.status();assert not r["maintenance"]
        return r
    def bad_header():
        auth(2)
        client.serial.write(HEADER.pack(MAGIC,1,CHUNK,65535,17))
        r=client.status();assert not r["maintenance"]
        return r
    def failure_locks():
        auth(2)
        r=denied_upload(lambda p,q:(b"\x80"*20,q))
        assert not client.status()["maintenance"]
        try:client.request(3,43)
        except Denied:return r
        raise AssertionError("failed proof left maintenance enabled")
    def invalid_credentials():
        ident,ctx,_=client.request(1)
        directory=ROOT/"artifacts"/"credential-negative"
        directory.mkdir(parents=True,exist_ok=True)
        data=json.loads(wallet.read_text())
        for name,mutation in (
            ("unauthorized",lambda w:w["secret"].__setitem__(0,(w["secret"][0]+1)%0x78000001)),
            ("bad-path",lambda w:w["siblings"][0].__setitem__(0,(w["siblings"][0][0]+1)%0x78000001)),
            ("revoked-epoch",lambda w:w.__setitem__("epoch",w["epoch"]+1))):
            altered=json.loads(json.dumps(data));mutation(altered)
            credential=directory/(name+".json");credential.write_text(json.dumps(altered))
            context=directory/(name+"-context.bin");context.write_bytes(ctx)
            completed=subprocess.run([str(BINARY),"prove",str(credential),str(context),
                str(directory/(name+"-proof.bin")),str(directory/(name+"-public.bin"))],capture_output=True)
            assert completed.returncode!=0,name
        client.exchange(ABORT,ident)
        return {"invalid_secret":True,"bad_path":True,"stale_epoch":True,"scope":"host witness validation"}
    def expired_challenge():
        ident,_,ttl=client.request(1);time.sleep(ttl/1000+0.3)
        r=result(client.exchange(FINISH,ident))
        assert r["code"] in (2,3) and not r["accepted"]
        return r
    def expired_maintenance():
        entered=auth(2);time.sleep(client.info()["maintenance_ttl_ms"]/1000+0.3)
        assert not client.status()["maintenance"]
        try:client.request(3,43)
        except Denied as e:return e.result
        raise AssertionError("expired maintenance accepted")
    try:
        assert client.info()["ready"]==1
        record("unauthorized_direct_command",direct_denied)
        record("authorized_credential",auth)
        record("all_maintenance_operations_and_second_member",positive_workflow)
        def flip_proof(p,q):p[8]^=1;return p,q
        def flip_root(p,q):q[0]^=1;return p,q
        def flip_nullifier(p,q):q[24]^=1;return p,q
        record("modified_proof",lambda:denied_upload(flip_proof))
        record("modified_registry_root",lambda:denied_upload(flip_root))
        record("modified_public_nullifier",lambda:denied_upload(flip_nullifier))
        record("malformed_proof",lambda:denied_upload(lambda p,q:(b"\x80"*20,q)))
        record("proof_replay_and_new_challenge_binding",replay)
        record("different_operation",different_operation)
        record("oversized_proof",oversized)
        record("out_of_order_chunk",wrong_offset)
        record("interrupted_transfer_timeout",interrupted)
        record("oversized_frame_closes_maintenance",bad_header)
        record("failed_proof_closes_maintenance",failure_locks)
        record("invalid_credential_path_and_epoch",invalid_credentials)
        if long:
            record("expired_challenge",expired_challenge)
            record("expired_maintenance_authorization",expired_maintenance)
        return records
    finally:
        client.close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--port",required=True)
    parser.add_argument("--long",action="store_true")
    parser.add_argument("--output",type=Path,default=ROOT/"docs/device-test-results.json")
    args=parser.parse_args();records=run(args.port,args.long)
    args.output.write_text(json.dumps(records,indent=2),encoding="utf-8")
    print(f"PASS {len(records)} hardware test groups",flush=True)
if __name__=="__main__":main()

