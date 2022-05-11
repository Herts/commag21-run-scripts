import comp
import time
from ED_benchmark_comp import run_experimental_design, int, float, str

def get_path_cfgs_asym_func(v, **kwargs):
    mqs_1_up = int(1.5 * (((v['bw_a_up'] * 1000000) / 8)) * (2 * v['delay_ms_a_up'] / 1000.0))  # 1.5 * BDP, TODO: This assumes that packet size is 1200 bytes
    mqs_1_down = int(1.5 * (((v['bw_a_down'] * 1000000) / 8)) * (2 * v['delay_ms_a_down'] / 1000.0))  # 1.5 * BDP, TODO: This assumes that packet size is 1200 bytes
    path_1_cfg = {
        "up_bw": v["bw_a_up"], "down_bw": v["bw_a_down"],
        "up_max_queue_size": mqs_1_up, "down_max_queue_size": mqs_1_down,
        "up_delay": v["delay_ms_a_up"], "down_delay": v["delay_ms_a_down"],
    }
    
    mqs_2_up = int(1.5 * (((v['bw_b_up'] * 1000000) / 8)) * (2 * v['delay_ms_b_up'] / 1000.0))  # 1.5 * BDP, TODO: This assumes that packet size is 1200 bytes
    mqs_2_down = int(1.5 * (((v['bw_b_down'] * 1000000) / 8)) * (2 * v['delay_ms_b_down'] / 1000.0))  # 1.5 * BDP, TODO: This assumes that packet size is 1200 bytes
    path_2_cfg = {
        "up_bw": v["bw_b_up"], "down_bw": v["bw_b_down"],
        "up_max_queue_size": mqs_2_up, "down_max_queue_size": mqs_2_down,
        "up_delay": v["delay_ms_b_up"], "down_delay": v["delay_ms_b_down"],
    }
    
    to_return = {'path_1_cfg': path_2_cfg, 'path_2_cfg': path_1_cfg}
    return to_return


def run_multipath_xp(nodes, test_name, setup_nets_opts, store_result_in_db_func, **kwargs):
    multipath = setup_nets_opts.get('multipath', False)
    
    server_logs = ""
    if setup_nets_opts.get("log_server", False):
        server_logs = "&> {}".format(setup_nets_opts["log_server"])

    def relaunch_config():
        comp.run_cmd_on_client(nodes, 'pkill picoquic')
        comp.run_cmd_on_server(nodes, 'pkill picoquic')
        comp.run_cmd_on_client(nodes, 'pkill ab')
        comp.run_cmd_on_server(nodes, 'pkill lighttpd')
        comp.run_cmd_on_client(nodes, 'pkill client')
        comp.run_cmd_on_server(nodes, 'pkill server')
        comp.run_cmd_on_client(nodes, 'rm -rf /tmp/*.log /tmp/cache*')
        comp.run_cmd_on_server(nodes, 'rm -rf /tmp/*.log /tmp/random*')

        comp.run_cmd_on_client(nodes, 'sysctl net.mptcp.mptcp_enabled={}'.format(1 if multipath else 0))
        comp.run_cmd_on_server(nodes, 'sysctl net.mptcp.mptcp_enabled={}'.format(1 if multipath else 0))

        comp.run_cmd_on_client(nodes, 'sysctl net.ipv4.tcp_no_metrics_save=1')
        comp.run_cmd_on_server(nodes, 'sysctl net.ipv4.tcp_no_metrics_save=1')

        comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')
        comp.run_cmd_on_client(nodes, 'pkill python')
        comp.run_cmd_on_server(nodes, 'pkill https_server')
        time.sleep(1)
        # Unfortunalely, it is a very complicated command, so provide the array directly
        comp.run_cmd_on_server(nodes, ["sh", "-c", "'python https_server.py server.pem {}'".format(server_logs)], daemon=True)
        time.sleep(1)

    relaunch_config()
    file_sizes = kwargs['file_sizes']
    for size in file_sizes:
        print "file size %d" % size

        # Generate random file at server side
        comp.run_cmd_on_server(nodes, 'dd if=/dev/zero of=random bs=1K count={}'.format(size // 1000))

        def run():
            server_ip = '10.2.1.1'

            # Empty the buffers and let the server start quietly
            time.sleep(0.2)

            # Ugly with python 2
            client_cmd = "curl -so /dev/null --insecure -w '%{time_total}\n' https://" + server_ip + "/random &> /tmp/log_client.log"
            err = comp.run_cmd_on_client(nodes, client_cmd)

            if err != 0:
                print("client returned err %d" % err)
                relaunch_config()
                return 0

            # Get the file to access it
            comp.scp_file_from_client(nodes, '/tmp/log_client.log', 'log_client.log')
            log_client = open('log_client.log')
            lines = log_client.readlines()
            elapsed_s_str = lines[0].strip()
            elapsed_ms = 1000.0 * float(elapsed_s_str)
            print "elapsed: %s milliseconds for %s" % (elapsed_ms, test_name)
            return elapsed_ms

        results = list(filter(lambda x: x, sorted(run() for _ in range(9))))
        results = [r for r in results if r > 0]
        avg = sum(results) / len(results) if results else 0
        median = results[int(len(results)/2)] if results else 0
        std_dev = sum(abs(x - avg) for x in results) / len(results) if results else 0
        print "median = %dms, avg = %dms, std_dev = %dms" % (median, avg, std_dev)
        store_result_in_db_func([test_name, median, std_dev, size, len(results)])

    comp.run_cmd_on_server(nodes, 'pkill picoquicdemo')
    comp.run_cmd_on_server(nodes, 'pkill https_server')


if __name__ == "__main__":
    test_nets_opts = {
        'tcp': {'multipath': False, 'log_server': "/dev/null"},
        'mptcp': {'multipath': True, 'log_server': "/dev/null"},
    }
    ranges = {
        "bw_a_up": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        "bw_a_down": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        #"loss_a": {"range": [0.1, 2], "type": float, "count": 1},  # %, TODO: Characterise typical losses with LTE
        "delay_ms_a_up": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
        "delay_ms_a_down": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
        "bw_b_up": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        "bw_b_down": {"range": [5.0, 50.0], "type": float, "count": 1},  # Mbps
        # "loss_b": {"range": [0.01, 1], "type": float, "count": 1},  # %
        "delay_ms_b_up": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
        "delay_ms_b_down": {"range": [2.5, 25.0], "type": float, "count": 1},  # ms
    }
    additional_columns = [('test_name', str), ('elapsed_time', float), ('std_dev_time', float), ('file_size', int), ('num_xps', int)]
    xp_kwargs = {'file_sizes': (10000000,)}

    run_experimental_design(test_nets_opts, ranges, run_multipath_xp,
                            db_filename='results_mptcp_asym_rev.db',
                            additional_columns=additional_columns,
                            get_path_cfgs_func=get_path_cfgs_asym_func,
                            xp_kwargs=xp_kwargs)
