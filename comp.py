import ipaddress
import subprocess

TC_EXEC = "~/iproute2-4.18.0/tc/tc" #"tc"

IPv4Prefix = '10.0.0.0/8'
IPv6Prefix = '2042::/16'
links = {
    'comp1': {
        'comp4': {
            'ip': '10.0.1.2/24',
            'ip6s': ['2042:0:1::2/64'],
            'ifname': 'eth1'
        },
        'comp5': {
            'ip': '10.1.1.2/24',
            'ip6s': ['2042:1:1::2/64'],
            'ifname': 'eth2'
        }
    },
    'comp2': {
        'comp4': {
            'ip': '10.3.0.2/24',
            'ip6s': ['2042:3:0::2/64'],
            'ifname': 'eth1'
        }
    },
    'comp3': {
        'comp4': {
            'ip': '10.0.2.2/24',
            'ip6s': ['2042:0:2::2/64'],
            'ifname': 'eth1'
        },
        'comp5': {
            'ip': '10.1.2.2/24',
            'ip6s': ['2042:1:2::2/64'],
            'ifname': 'eth2'
        }
    },
    'comp4': {
        'comp1': {
            'ip': '10.0.1.1/24',
            'ip6s': ['2042:0:1::1/64'],
            'ifname': 'eth1'
        },
        'comp3': {
            'ip': '10.0.2.1/24',
            'ip6s': ['2042:0:2::1/64'],
            'ifname': 'eth2'
        },
        'comp2': {
            'ip': '10.3.0.1/24',
            'ip6s': ['2042:3:0::1/64'],
            'ifname': 'eth3'
        }
    },
    'comp5': {
        'comp1': {
            'ip': '10.1.1.1/24',
            'ip6s': ['2042:1:1::1/64'],
            'ifname': 'eth3'
        },
        'comp3': {
            'ip': '10.1.2.1/24',
            'ip6s': ['2042:1:2::1/64'],
            'ifname': 'eth1'
        },
        'comp6': {
            'ip': '10.2.1.2/24',
            'ip6s': ['2042:2:1::2/64'],
            'ifname': 'eth2'
        }
    },
    'comp6': {
        'comp5': {
            'ip': '10.2.1.1/24',
            'ip6s': ['2042:2:1::1/64'],
            'ifname': 'eth1'
        }
    }
}

routes = {
    'comp1': {
        '10.2.1.0/24': {'via': '10.1.1.1', 'dev': 'eth1'},
        '10.3.0.0/24': {'via': '10.0.1.1', 'dev': 'eth2'},
        # '2042:2::/32': {'via': '2042:1:1::1'},
        # '2042:3::/32': {'via': '2042:0:1::1'},
        # '2042:1::/32':   {'via': '2042:1:1::1'},
        # '2042::/32':     {'via': '2042:0:1::1'}
    },
    'comp2': {
        '10.0.0.0/8':  {'via': '10.3.0.1', 'dev': 'eth1'},
        # '2042::/16':   {'via': '2042:3:0::1'}
    },
    'comp3': {
        '10.2.1.0/24': {'via': '10.1.2.1', 'dev': 'eth2'},
        '10.3.0.0/24': {'via': '10.0.2.1', 'dev': 'eth1'},
        # '2042:2::/32': {'via': '2042:1:2::1'},
        # '2042:3::/32': {'via': '2042:0:2::1'},
        # '2042:1::/32':   {'via': '2042:1:2::1'},
        # '2042::/32':     {'via': '2042:0:2::1'}
    },
    'comp4': {
        ('10.0.0.0/8', 100): {'via': '10.0.1.2', 'dev': 'eth1'},
        ('10.0.0.0/8', 101): {'via': '10.0.2.2', 'dev': 'eth2'},
        # ('2042::/16', 100): {'via': '2042:0:1::2'},
        # ('2042::/16', 101): {'via': '2042:0:2::2'},
        # '2042:1:1::/64':    {'via': '2042:0:1::2'},
        # '2042:1:2::/64':    {'via': '2042:0:2::2'}
    },
    'comp5': {
        '10.0.1.0/24': {'via': '10.1.1.2', 'dev': 'eth2'},
        '10.0.2.0/24': {'via': '10.1.2.2', 'dev': 'eth1'},
        ('10.0.0.0/8', 100): {'via': '10.1.1.2'},
        ('10.0.0.0/8', 101): {'via': '10.1.2.2'},
        # ('2042::/16', 100): {'via': '2042:1:1::2'},
        # ('2042::/16', 101): {'via': '2042:1:2::2'},
        # '2042:0:1::/64':    {'via': '2042:1:1::2'},
        # '2042:0:2::/64':    {'via': '2042:1:2::2'}
    },
    'comp6': {
        '10.0.0.0/16': {'via': '10.2.1.2', 'dev': 'eth1'},
        '10.0.0.0/8':  {'via': '10.2.1.2', 'dev': 'eth1'},
        # '2042::/32':   {'via': '2042:2:1::2'},
        # '2042::/16':   {'via': '2042:2:1::2'}
    }
}

source_routes = {
    'comp4': {
        '10.0.1.1': {'10.2.1.0/24': {'dev': 'eth1'},
                     'default':     {'via': '10.0.1.2', 'dev': 'eth1'}},
        '10.0.2.1': {'10.2.1.0/24': {'dev': 'eth2'},
                     'default':     {'via': '10.0.2.2', 'dev': 'eth2'}},
    }
}


def ipv4_to_int(ipv4):
    split = ipv4.split('.')
    if len(split) != 4:
        return None
    retval = 0
    retval += int(split[0]) << 24
    retval += int(split[1]) << 16
    retval += int(split[2]) << 8
    retval += int(split[3])
    return retval


def tc_delete_cmd(ifname):
    return "{0} qdisc del dev {1} root; {0} qdisc del dev {1} clsact; {0} qdisc del dev {1} ingress".format(TC_EXEC, ifname)

def tc_dropper_reset(ifname):
    cmds = [
        "%s qdisc del dev %s clsact" % (TC_EXEC, ifname),
        "%s qdisc add dev %s clsact" % (TC_EXEC, ifname),
        '%s filter add dev %s egress bpf obj ebpf_dropper/ebpf_dropper_egress.o section action direct-action' % (TC_EXEC, ifname)
    ]
    return cmds


def tc_dropper_commands(ifname, parent, loss=None, seed=None, port_to_watch=None, server_ip=None, client_ip=None, node=None, **kwargs):
    if node.name in ["comp1", "comp3"]:
        seed_egress = seed + 42
    else:
        seed_egress = seed
    print("node name = ", node.name)
    flags_egress = "-f ebpf_dropper_egress.o --seed {} --ips {},{} --port {}".format(seed_egress, server_ip, client_ip,
                                                                                     port_to_watch)
    loss_flags = "-P {}".format(loss)
    cmd_egress = """pushd ebpf_dropper ; python3 attach_dropper.py --udp {} {} ; popd""".format(loss_flags, flags_egress)


    cmds = [
        "%s qdisc del dev %s clsact" % (TC_EXEC, ifname),
        "%s qdisc add dev %s clsact" % (TC_EXEC, ifname),
        "rm -f ebpf_dropper/ebpf_dropper*.o",
        cmd_egress,
        '%s filter add dev %s egress bpf obj ebpf_dropper/ebpf_dropper_egress.o section action direct-action' % (TC_EXEC, ifname)
    ]

    return cmds


def tc_delay_cmd(ifname, parent, delay=None, jitter=None, loss=None, max_queue_size=None, **kwargs):
    max_queue_size_pkt = None
    if max_queue_size:
        max_queue_size_pkt = max(max_queue_size // 1200, 10)
    netem_args = "{}{}{}{}".format(
        "delay {}ms ".format(delay) if delay is not None and delay > 0.0 else "",
        "{} ".format(jitter) if jitter is not None and jitter > 0.0 else "",
        "loss random {} ".format(loss) if loss is not None and loss > 0.0 else "",
        "limit 1000000",
    )
    if not netem_args:
        return ""

    return "{} qdisc add dev {} parent {} handle 10: netem {}".format(TC_EXEC, ifname, parent, netem_args)


def tc_bw_cmds(ifname, bw, max_queue_size=15000, **kwargs):
    if max_queue_size <= 15000:
        max_queue_size = 15000
    cmds = []
    cmds.append("{} qdisc add dev {} root handle 5:0 htb default 1".format(TC_EXEC, ifname))
    cmds.append("{} class add dev {} parent 5:0 classid 5:1 htb rate {}Mbit burst {}".format(TC_EXEC, ifname, bw, max_queue_size))
    # If we have asymmetric links, the policing command should be adapted
    cmds.append("{tc} qdisc add dev {ifname} handle ffff: ingress".format(tc=TC_EXEC, ifname=ifname))
    if "abw" in kwargs:
        # Asymmetric link
        abw = kwargs['abw']
        amqs = kwargs.get("amax_queue_size", 15000)
        if amqs <= 15000:
            amqs = 15000
        cmds.append("{tc} filter add dev {ifname} parent ffff: u32 match u32 0 0 police rate {bw}mbit burst {mqs} drop".format(tc=TC_EXEC, ifname=ifname, bw=abw, mqs=amqs))
    else:
        # Symmetric link
        cmds.append("{tc} filter add dev {ifname} parent ffff: u32 match u32 0 0 police rate {bw}mbit burst {mqs} drop".format(tc=TC_EXEC, ifname=ifname, bw=bw, mqs=max_queue_size))
        #cmds.append("{} qdisc add dev {} root handle 5:0".format(TC_EXEC, ifname))
    return cmds


def tc_cmds(ifname, bw, use_dropper=False, seed=None, server_port=None, server_ip=None, client_ip=None, node=None, **kwargs):
    cmds = tc_bw_cmds(ifname, bw, **kwargs)
    if use_dropper:
        # the loss should not be performed by netem
        loss = kwargs.pop("loss")
    delay_cmd = tc_delay_cmd(ifname, parent="5:1", **kwargs)
    # delay_cmd = tc_delay_cmd(ifname, root="5:0", **kwargs)
    if delay_cmd:
        cmds.append(delay_cmd)
    if use_dropper:
        cmds.extend(tc_dropper_commands(ifname, None, loss=loss, seed=seed, port_to_watch=server_port,
                                        server_ip=server_ip, client_ip=client_ip, node=node))
    return cmds


class CompNode:
    user = "root"

    def __init__(self, name, links, routes={}, source_routes={}, v4=True, v6=True):
        self.name = name
        self.links = links
        self.routes = routes
        self.source_routes = source_routes
        self.v4 = v4
        self.v6 = v6

    def run_cmd_daemon(self, cmd_array):
        cmd = ["ssh", "-S", "none", "-f", "-n", "{}@{}".format(self.user, self.name)] + cmd_array
        print cmd

        return subprocess.call(cmd)

    def run_cmd(self, cmd, daemon=False):
        # In daemon mode, we cannot split the command in advance...
        if daemon:
            return self.run_cmd_daemon(cmd)
        print(cmd)
        # print """ssh {}@{} {}""".format(self.user, self.name, cmd)
        return subprocess.call(['ssh', '{}@{}'.format(self.user, self.name), cmd])

    def scp_file_from_node(self, from_filename, to_filename):
        # print "scp {}@{}:{} {}".format(self.user, self.name, from_filename, to_filename)
        return subprocess.call(['scp', '{}@{}:{}'.format(self.user, self.name, from_filename), to_filename])

    def setup_links(self):
        self.run_cmd("ip -4 route flush root {}".format(IPv4Prefix))
        self.run_cmd("ip -6 route flush root {}".format(IPv6Prefix))
        for peer, link in self.links.items():
            ifname, ip, ip6s = link['ifname'], link['ip'], link['ip6s']
            addrs = []
            if self.v4:
                addrs.append(ip)
            if self.v6:
                addrs.extend(ip6s)
            print "{}: Setup interface {} to {} with addrs {}".format(self.name, ifname, peer, ", ".join(addrs))
            self.run_cmd("ifconfig {} up".format(ifname))
            self.run_cmd("ip addr flush scope global dev {}".format(ifname))
            for addr in addrs:
                self.run_cmd("ip addr add {} dev {}".format(addr, ifname))
            # And drop previous configuration
            self.run_cmd(tc_delete_cmd(ifname))
            # Disable TSO, GSO and GRO
            self.run_cmd("ethtool -K {} tso off".format(ifname))
            self.run_cmd("ethtool -K {} gso off".format(ifname))
            self.run_cmd("ethtool -K {} gro off".format(ifname))

        for target, how in self.routes.items():
            metric = ""
            if isinstance(target, tuple):
                target, metric = target[0], "metric {}".format(target[1])

            if ipaddress.ip_network(unicode(target)).version == 4 and not self.v4 \
                    or ipaddress.ip_network(unicode(target)).version == 6 and not self.v6:
                continue

            via, dev = how['via'], how.get('dev', None)
            dev_text = "dev {}".format(dev) if dev else ""
            print "{}: Setup route to {} via {} {} {}".format(self.name, target, via, dev_text, metric)
            self.run_cmd("ip route add {} via {} {} {}".format(target, via, dev_text, metric))

        table_num = 0
        for src, routes in self.source_routes.items():
            table_num += 1
            # First delete ALL rules, otherwise say bye bye to perfs...
            self.run_cmd("while ip rule delete from 0/0 to 0/0 table {} 2>/dev/null; do true; done".format(table_num))
            self.run_cmd("while ip -6 rule delete from ::/0 to ::/0 table {} 2>/dev/null; do true; done"
                         .format(table_num))

            if ipaddress.ip_network(unicode(src)).version == 4 and not self.v4 \
                    or ipaddress.ip_network(unicode(src)).version == 6 and not self.v6:
                continue
            # Here is now the source routing
            self.run_cmd("ip rule add from {} table {}".format(src, table_num))
            for target, how in routes.items():
                via, dev = how.get('via', None), how.get('dev', None)
                via_text = "via {}".format(via) if via else ""
                dev_text = "dev {}".format(dev) if dev else ""
                print "{}: Setup source route from {} target {} {} {}".format(self.name, src, target, via_text, dev_text)
                self.run_cmd("ip route add {} {} {} table {}".format(target, via_text, dev_text, table_num))

        # Don't forget to forward packets
        self.run_cmd("sysctl -w net.ipv4.conf.all.forwarding=1")
        self.run_cmd("sysctl -w net.ipv6.conf.all.forwarding=1")
        # Proxy ARP, required for some nodes
        self.run_cmd("sysctl -w net.ipv4.conf.all.proxy_arp=1")
        # Activate SRv6
        self.run_cmd("sysctl -w net.ipv6.conf.all.seg6_enabled=1")
        self.run_cmd("sysctl -w net.ipv6.conf.default.seg6_enabled=1")
        for neighbor_dic in links[self.name].values():
            self.run_cmd("sysctl -w net.ipv6.conf.{}.seg6_enabled=1".format(neighbor_dic["ifname"]))
        # Disable MPTCP if we are on a mptcp kernel
        self.run_cmd("sysctl -w net.mptcp.mptcp_enabled=0")

    def configure_link(self, to, bw, **kwargs):
        ifname = self.links[to]['ifname']
        # First drop previous configuration
        self.run_cmd(tc_delete_cmd(ifname))
        # Then apply new commands
        link_cmds = tc_cmds(ifname, bw, node=self, **kwargs)
        for link_cmd in link_cmds:
            print link_cmd
            self.run_cmd(link_cmd)

    def ping_using_all_links(self, to_ip):
        for link in self.links.values():
            ifname = link['ifname']
            self.run_cmd("ping -c 5 -i 0.1 -I {} {}".format(ifname, to_ip))


def get_up_and_down_path_cfg(path_cfg):
    up_path_cfg = {
        "bw": path_cfg["up_bw"], "max_queue_size": path_cfg.get("up_max_queue_size", 15000),
        "abw": path_cfg["down_bw"], "amax_queue_size": path_cfg.get("down_max_queue_size", 15000),
        "delay": path_cfg["up_delay"], "loss": path_cfg.get("up_loss", 0),
    }
    down_path_cfg = {
        "bw": path_cfg["down_bw"], "max_queue_size": path_cfg.get("down_max_queue_size", 15000),
        "abw": path_cfg["up_bw"], "amax_queue_size": path_cfg.get("up_max_queue_size", 15000),
        "delay": path_cfg["down_delay"], "loss": path_cfg.get("down_loss", 0),   
    }
    return up_path_cfg, down_path_cfg


def get_comp_nodes(path_1_cfg={'bw': 10000}, path_2_cfg=None, v4=True, v6=True):
    nodes = {}
    nodes['comp4'] = CompNode('comp4', links['comp4'], routes=routes.get('comp4', {}),
                              source_routes=source_routes.get('comp4', {}), v4=v4, v6=v6)
    nodes['comp1'] = CompNode('comp1', links['comp1'], routes=routes.get('comp1', {}), v4=v4, v6=v6)
    nodes['comp3'] = CompNode('comp3', links['comp3'], routes=routes.get('comp3', {}), v4=v4, v6=v6)
    nodes['comp5'] = CompNode('comp5', links['comp5'], routes=routes.get('comp5', {}), v4=v4, v6=v6)
    nodes['comp6'] = CompNode('comp6', links['comp6'], routes=routes.get('comp6', {}), v4=v4, v6=v6)
    nodes['comp2'] = CompNode('comp2', links['comp2'], routes=routes.get('comp2', {}), v4=v4, v6=v6)

    for node in nodes.values():
        node.setup_links()

    ASYM_VALUES = ["up_bw", "up_delay", "down_bw", "down_delay"]

    # Configure path 1
    # /!\ Need to handle asymmetric paths
    if all(v in path_1_cfg for v in ASYM_VALUES):
        up_path_1_cfg, down_path_1_cfg = get_up_and_down_path_cfg(path_1_cfg)
        nodes['comp1'].configure_link('comp5', **up_path_1_cfg)
        nodes['comp1'].configure_link('comp4', **down_path_1_cfg)
    else:
        nodes['comp1'].configure_link('comp5', **path_1_cfg)
        nodes['comp1'].configure_link('comp4', **path_1_cfg)
    if path_1_cfg.get("use_dropper", False):
        for cmd in tc_dropper_commands(nodes['comp5'].links['comp1']['ifname'], loss=path_1_cfg["loss"], seed=path_1_cfg["seed"],
                                       port_to_watch=path_1_cfg["server_port"], server_ip=path_1_cfg["server_ip"],
                                       client_ip=path_1_cfg["client_ip"], node=nodes["comp5"], parent=None,
                                       use_dropper=path_1_cfg["use_dropper"]):
            nodes["comp5"].run_cmd(cmd)

    # Configure path 2
    if path_2_cfg:
        if all(v in path_1_cfg for v in ASYM_VALUES):
            up_path_2_cfg, down_path_2_cfg = get_up_and_down_path_cfg(path_2_cfg)
            nodes['comp3'].configure_link('comp5', **up_path_2_cfg)
            nodes['comp3'].configure_link('comp4', **down_path_2_cfg)
        else:
            nodes['comp3'].configure_link('comp5', **path_2_cfg)
            nodes['comp3'].configure_link('comp4', **path_2_cfg)

    # Ping all possible paths using two commands, to avoid ARP issues
    if v4:
        nodes['comp4'].ping_using_all_links('10.2.1.1')

    # Return the configured nodes
    return nodes


def run_cmd_on_server(nodes, cmd, **kwargs):
    return nodes['comp6'].run_cmd(cmd, **kwargs)


def run_cmd_on_client(nodes, cmd, **kwargs):
    return nodes['comp4'].run_cmd(cmd, **kwargs)


def scp_file_from_client(nodes, from_filename, to_filename):
    return nodes['comp4'].scp_file_from_node(from_filename, to_filename)


def scp_file_from_server(nodes, from_filename, to_filename):
    return nodes['comp6'].scp_file_from_node(from_filename, to_filename)
