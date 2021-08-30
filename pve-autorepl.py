#!/usr/bin/python3

import argparse
import json
import subprocess

hostname = open("/etc/hostname", "r").read().strip()
replication_map = {}
root_email = ""
auto_ha = False

def init():
    global auto_ha, replication_map, root_email
    # parse arguments
    parser = argparse.ArgumentParser(description='Find VM that configured for autoloading and\
        setup replication and high availability')
    parser.add_argument('-a', '--ha', action='store_true', help='enable auto high availability')
    args = parser.parse_args()
    auto_ha = args.ha
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


def log(msg):
    print(msg)

def sendmail(subject: str, body: str):
    body_str_encoded_to_byte = body.encode()
    output = subprocess.run(["mail", "-s", subject, root_email], input=body_str_encoded_to_byte, capture_output=True)
    if output.stderr.decode("utf-8") != "":
        print(f'Error sendmail(): {output.stderr.decode("utf-8")}')
        exit(1)


def get_repl_vmids():
    cmd = 'pvesh get /cluster/replication --output-format json-pretty'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    js = json.loads(output.stdout)
    vmid_list = []
    for obj in js:
        if obj['source'] == hostname:
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

def get_ha_vmids():
    cmd = 'pvesh get /cluster/ha/resources --output-format json-pretty'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    js = json.loads(output.stdout)
    vmid_list = []
    for obj in js:
        if obj['group'] == hostname:
            sid = obj['sid']
            vmid = sid.split(":")[1]
            vmid_list.append(vmid)
    return vmid_list

def get_qm_need_ha_vmids():
    vm_list_replicated = get_repl_vmids()
    vm_list_ha = get_ha_vmids()
    vm_list_need_ha = []
    for vmid in vm_list_replicated:
        if vmid not in vm_list_ha:
            vm_list_need_ha.append(vmid)

    return vm_list_need_ha

def enable_qm_ha(vmid):
    cmd = f'ha-manager add vm:{vmid} --max_relocate=1 --max_restart=1 --group={hostname}'
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if output.stderr != "":
        log(f'Error: enable_qm_replication({vmid}): {output.stderr}')
    else:
        log(f'Success: enable_qm_replication({vmid})')

def setup_ha_groups():
    # Check if high availability is needed for localhost
    if hostname in replication_map:
        # get current ha groups
        cmd = f'pvesh get /cluster/ha/groups --output-format json-pretty'
        output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        js = json.loads(output.stdout)
        # search localhost in current ha groups
        for obj in js:
            if obj['group'] == hostname:
                return # ha group for this server already exist
        # setup ha group for localhost
        msg =f"Setup new replication group: {hostname}:2,{replication_map[hostname]}:1"
        sendmail(f"{hostname} pve-autorepl", msg)
        cmd = f'ha-manager groupadd {hostname} -nodes {hostname}:2,{replication_map[hostname]}:1 -nofailback -restricted'
        output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if output.stderr != "":
            log(f'Error: {msg}')
        else:
            log(f'Success: {msg}')

if __name__ == '__main__':
    init()

    # enable replication for new vm's which starts on boot
    vmid_list = get_qm_need_replication_vmids()
    if len(vmid_list) != 0:
        msg = f"Found {len(vmid_list)} vm needs to replication: {vmid_list}"
        log(msg)
        sendmail(f"{hostname} pve-autorepl", msg)
        for vmid in vmid_list:
            enable_qm_replication(vmid)
    # setup HA groups by replication-map.json
    setup_ha_groups()
    # enable HA for new replicated VM's
    vmid_list = get_qm_need_ha_vmids()
    if len(vmid_list) != 0:
        msg =f"Found {len(vmid_list)} vm needs to enable HA: {vmid_list}"
        log(msg)
        sendmail(f"{hostname} pve-autorepl", msg)
        for vmid in vmid_list:
            enable_qm_ha(vmid)

