"""Reproducible real-board benchmark; no simulated values."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import platform
import re
import statistics
import time
from prover.transport import Client
from prover.usb import generate, ROOT

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",required=True)
    parser.add_argument("--count",type=int,default=5)
    parser.add_argument("--output",type=Path,default=ROOT/"docs/benchmark-results.json")
    args=parser.parse_args()
    if args.count<1 or args.count>100:raise ValueError("count 1..100")
    client=Client(args.port); samples=[]
    try:
        info=client.info()
        if not info["ready"]:raise RuntimeError("device not ready")
        for index in range(args.count):
            start=time.perf_counter()
            ident,context,_=client.request(1)
            proof,public,host,_=generate(ROOT/"secrets/demo/credential-0.json",context)
            result=client.upload(ident,proof,public)
            if result["code"] or not result["accepted"]:raise RuntimeError(result)
            result["host"]=host;result["host_total_ms"]=round((time.perf_counter()-start)*1000,3)
            samples.append(result)
            print(json.dumps({"sample":index+1,"verify_us":result["verify_us"],"proof_bytes":len(proof)}),flush=True)
    finally:client.close()
    binary=ROOT/"firmware/.pio/build/esp32-s3-devkitc-1/firmware.bin"
    sdkconfig=(ROOT/"firmware/sdkconfig.esp32-s3-devkitc-1").read_text()
    cpu_mhz=int(re.search(r"^CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ=(\d+)$",sdkconfig,re.M)[1])
    report={"date":datetime.now(timezone(timedelta(hours=-3))).isoformat(),
        "host":{"platform":platform.platform(),"processor":platform.processor(),"python":platform.python_version()},
        "device":{"chip":"ESP32-S3 rev 0.2","cpu_mhz":cpu_mhz,"cpu_frequency_source":"generated ESP-IDF sdkconfig; DFS disabled",
                  "flash_bytes":16777216,"psram_bytes":8388608,
                  "psram_mhz":40,"lcd_active":True,"port":args.port},
        "capabilities":info,
        "firmware_bytes":binary.stat().st_size,
        "firmware_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),
        "summary":{"samples":len(samples),"median_verify_ms":statistics.median(s["verify_us"]/1000 for s in samples),
                   "median_transfer_ms":statistics.median(s["host_transfer_ms"] for s in samples),
                   "median_host_generation_ms":statistics.median(s["host"]["generation_ms"] for s in samples),
                   "median_total_ms":statistics.median(s["host_total_ms"] for s in samples),
                   "min_proof_bytes":min(s["proof_bytes"] for s in samples),
                   "max_proof_bytes":max(s["proof_bytes"] for s in samples)},
        "samples":samples}
    args.output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report["summary"],indent=2))
if __name__=="__main__":main()

