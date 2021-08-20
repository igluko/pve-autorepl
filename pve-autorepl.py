#!/usr/bin/python3

import subprocess
import json

hostname = open("/etc/hostname", "r").read().strip()
replication_map = {}
root_email = ""

def init():
    global replication_map, root_email
    # Load replication map
    file = open("/root/Sync/replication-map.json", "r").read().strip()
    replication_map = json.loads(file)
    # Load root email
    cmd = "pvesh get /access/users/root@pam --output-format json-pretty"
    output = subprocess.run(cmd.split(), capture_output=True, text=True)
    if output.stderr != "":
        print(f'Error init(): {output.stderr}')
        exit(1)
    js = json.loads(output.stdout)
    root_email = js["email"]

def sendmail(subject: str, body: str):
    body_str_encoded_to_byte = body.encode()
    output = subprocess.run(["mail", "-s", subject, root_email], input=body_str_encoded_to_byte, capture_output=True)
    if output.stderr.decode("utf-8") != "":
        print(f'Error sendmail(): {output.stderr.decode("utf-8")}')
        exit(1)

def log(msg):
    print(msg)

def get_repl_vmids():
    cmd = 'pvesh get /cluster/replication --output-format json-pretty'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    js = json.loads(output.stdout)
    vmid_list = []
    for obj in js:
        vmid_list.append(obj['guest'])
    return vmid_list

 
def get_qm_local_vmids():
    cmd = f'pvesh get /nodes/{hostname}/qemu --output-format json-pretty'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    js = json.loads(output.stdout)
    vmid_list = []
    for obj in js:
        vmid_list.append(obj['vmid'])
    return vmid_list

def get_ct_local_vmids():
    cmd = f'pvesh get /nodes/{hostname}/lxc --output-format json-pretty'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    js = json.loads(output.stdout)
    vmid_list = []
    for obj in js:
        vmid_list.append(obj['vmid'])
    return vmid_list
    

def is_qm_vmid_autostart(vmid):
    cmd = f'pvesh get /nodes/{hostname}/qemu/{vmid}/config --output-format json-pretty'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # print (output.stdout)
    js = json.loads(output.stdout)
    if "onboot" in js:
        return js["onboot"] == 1
    else:
        return False

def get_qm_autostart_vmids():
    vmid_local_list = get_qm_local_vmids()
    vmid_autostart_list = []
    for vmid in vmid_local_list:
        if is_qm_vmid_autostart(vmid):
            vmid_autostart_list.append(vmid)
    return vmid_autostart_list

def enable_qm_replication(vmid):
    cmd = f'pvesr create-local-job {vmid}-0 {replication_map[hostname]} --schedule */15 --rate 50'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if output.stderr != "":
        log(f'Error: enable_qm_replication({vmid}): {output.stderr}')
    else:
        log(f'Success: enable_qm_replication({vmid})')

def get_qm_need_replication_vmids():
    vm_list_autostart = get_qm_autostart_vmids()
    vm_list_replicated = get_repl_vmids()
    
    vm_list_need_replication = []
    for vmid in vm_list_autostart:
        if vmid not in vm_list_replicated:
            vm_list_need_replication.append(vmid)

    return vm_list_need_replication


if __name__ == '__main__':
    init()

    # enable replication for new vm's which starts on boot
    vmid_list = get_qm_need_replication_vmids()
    if len(vmid_list) != 0:
        log(f"Founded {len(vmid_list)} vm needs to replication: {vmid_list}")
        sendmail(f"{hostname} pve-autorepl", f"Founded {len(vmid_list)} vm needs to replication: {vmid_list}")
        for vmid in vmid_list:
            enable_qm_replication(vmid)
