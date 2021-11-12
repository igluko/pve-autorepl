#!/usr/bin/python3

import argparse
import json
import subprocess

hostname = open("/etc/hostname", "r").read().strip()
replication_map = {}
root_email = ""
auto_ha = False
autostart = False
maxvmid = False
rate = ""
interval = "*/15"

def init():
    global auto_ha, replication_map, root_email, maxvmid, autostart, rate, interval
    # parse arguments
    parser = argparse.ArgumentParser(description='Find VM that configured for autoloading and\
        setup replication and high availability')
    parser.add_argument('--ha', action='store_true', help='enable auto high availability')
    parser.add_argument('--autostart', action='store_true', help='only vm which start on boot will be replicated')
    parser.add_argument("--maxvmid", help="maximum vmid number for replication", type=int)
    parser.add_argument("--rate", help="maximum rate in MB/s", type=int)
    parser.add_argument("--interval", help="interval in minutes, example */15 - every 15 minutes", type=str)
    args = parser.parse_args()
    auto_ha = args.ha
    maxvmid = args.maxvmid
    if args.rate:
        rate = '--rate ' + str(args.rate)
    if args.interval:
        interval = args.interval
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
    cmd = f'pvesr create-local-job {vmid}-0 {replication_map[hostname]} --schedule {interval} {rate}'
    print(cmd)
    output = subprocess.run(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if output.stderr != "":
        log(f'Error: enable_qm_replication({vmid}): {output.stderr}')
    else:
        log(f'Success: enable_qm_replication({vmid})')

def get_qm_not_replication_vmids():
    vm_list = get_qm_local_vmids()
    vm_list_has_replication = get_repl_vmids()
    
    vm_list_not_replication = []
    for vmid in vm_list:
        if vmid not in vm_list_has_replication:
            vm_list_not_replication.append(vmid)

    return vm_list_not_replication

def filter_qm_is_autostart(qm_list):
    vm_list_autostart = get_qm_autostart_vmids()

    vm_list_filtered = []
    for vmid in qm_list:
        if vmid in vm_list_autostart:
            vm_list_filtered.append(vmid)

    return vm_list_filtered

def filter_qm_in_list(qm_list, match_list):
    vm_list_filtered = []
    for vmid in qm_list:
        if int(vmid) in match_list:
            vm_list_filtered.append(vmid)
    return vm_list_filtered

def get_qm_need_replication_vmids():
    vm_list = get_qm_not_replication_vmids()
    if autostart:
        vm_list = filter_qm_is_autostart(vm_list)
    if maxvmid:
        vm_list = filter_qm_in_list(vm_list, range(maxvmid))
    return vm_list

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
    cmd = f'/usr/sbin/ha-manager add vm:{vmid} --max_relocate=1 --max_restart=1 --group={hostname}'
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
        cmd = f'/usr/sbin/ha-manager groupadd {hostname} -nodes {hostname}:2,{replication_map[hostname]}:1 -nofailback -restricted'
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
    if auto_ha:
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

