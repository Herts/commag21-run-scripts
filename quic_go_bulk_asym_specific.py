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
    
    to_return = {'path_1_cfg': path_1_cfg, 'path_2_cfg': path_2_cfg}
    return to_return

def generate_random_files(nodes, **kwargs):
    file_sizes = kwargs['file_sizes']
    for fs in file_sizes:
        # FIXME we should be able to set comp6 as being the 
        comp.run_cmd_on_server(nodes, "dd if=/dev/urandom of=/tmp/random_{} bs=1K count={}".format(fs, fs / 1000))

def run_quic_go_xp(nodes, test_name, setup_nets_opts, store_result_in_db_func, **kwargs):
    if not kwargs.get('first_run', True):
        generate_random_files(nodes, **kwargs)

    multipath = ""
    if setup_nets_opts.get('multipath', False):
        multipath = "-m"

    comp.run_cmd_on_client(nodes, 'pkill picoquic')
    comp.run_cmd_on_server(nodes, 'pkill picoquic')
    comp.run_cmd_on_client(nodes, 'pkill ab')
    comp.run_cmd_on_server(nodes, 'pkill lighttpd')
    comp.run_cmd_on_client(nodes, 'pkill client')
    comp.run_cmd_on_server(nodes, 'pkill server')
    comp.run_cmd_on_client(nodes, 'rm -rf /tmp/*.log /tmp/cache*')
    comp.run_cmd_on_server(nodes, 'rm -rf /tmp/*.log /tmp/random*')

    # Unfortunalely, it is a very complicated command, so provide the array directly
    comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd /tmp; nohup /root/quic-go/server -www /tmp -certpath /root/quic-go -bind 0.0.0.0:4443 2>&1 > /tmp/log_server.log'"], daemon=True)

    # Remove all caches
    comp.run_cmd_on_client(nodes, "rm -rf /tmp/cache_*")

    # Run a dummy XP just to get cache info
    comp.run_cmd_on_client(nodes, "cd /tmp; /root/quic-go/client -c https://10.2.1.1:4443/ploufiplof &> /tmp/log_client.log")

    file_sizes = kwargs['file_sizes']
    for size in file_sizes:
        print "file size %d" % size
        comp.run_cmd_on_server(nodes, 'dd if=/dev/urandom of=/tmp/random_{size} bs={size} count=1'.format(size=size))
        def run():
            server_ip = '10.2.1.1'

            client_cmd = 'cd /tmp; QUIC_GO_LOG_LEVEL=debug timeout 30 /root/quic-go/client {} -c https://{}:4443/random_{} &> /tmp/log_client.log'.format(multipath, server_ip, size)
            err = comp.run_cmd_on_client(nodes, client_cmd)

            if err != 0:
                print("client returned err %d" % err)
                comp.run_cmd_on_client(nodes, 'pkill client')
                comp.run_cmd_on_server(nodes, 'pkill server')
                # Unfortunalely, it is a very complicated command, so provide the array directly
                comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd /tmp; nohup /root/quic-go/server -www /tmp -certpath /root/quic-go -bind 0.0.0.0:4443 2>&1 > /tmp/log_server.log'"], daemon=True)

                # Remove all caches
                comp.run_cmd_on_client(nodes, "rm -rf /tmp/cache_*")

                # Run a dummy XP just to get cache info
                comp.run_cmd_on_client(nodes, "cd /tmp; timeout 10 /root/quic-go/client -c https://10.2.1.1:4443/ploufiplof &> /tmp/log_client.log")
                return 0

            # Get the file to access it
            comp.scp_file_from_client(nodes, '/tmp/log_client.log', 'log_client.log')
            log_client = open('log_client.log')
            lines = log_client.readlines()

            time_raw = lines[-1]
            elapsed_ms = None
            try:
                if "ms" in time_raw:
                    elapsed_ms = float(time_raw.split("ms")[0])
                elif "m" in time_raw:
                    splitted = time_raw.split("m")
                    elapsed_ms =  float(splitted[0]) * 60.0 * 1000.0 + float(splitted[1].split("s")[0]) * 1000.0
                else:
                    elapsed_ms = float(time_raw.split("s")[0]) * 1000.0
            except Exception:
                pass

            if not elapsed_ms or elapsed_ms <= 0.0:
                print lines[-1]
                print "Error for this run..."
                comp.run_cmd_on_client(nodes, 'pkill client')
                comp.run_cmd_on_server(nodes, 'pkill server')
                 # Unfortunalely, it is a very complicated command, so provide the array directly
                comp.run_cmd_on_server(nodes, ["sh", "-c", "'cd /tmp; nohup /root/quic-go/server -www /tmp -certpath /root/quic-go -bind 0.0.0.0:4443 2>&1 > /tmp/log_server.log'"], daemon=True)

                # Remove all caches
                comp.run_cmd_on_client(nodes, "rm -rf /tmp/cache_*")

                # Run a dummy XP just to get cache info
                comp.run_cmd_on_client(nodes, "cd /tmp; timeout 10 /root/quic-go/client -c https://10.2.1.1:4443/ploufiplof &> /tmp/log_client.log")
                return 0

            time.sleep(0.02)
            print "elapsed: {} milliseconds for {}".format(elapsed_ms, test_name)
            return elapsed_ms

        results = list(filter(lambda x: x, sorted(run() for _ in range(1))))
        results = [r for r in results if r > 0]
        avg = sum(results) / len(results) if results else 0
        median = results[int(len(results)/2)] if results else 0
        std_dev = sum(abs(x - avg) for x in results) / len(results) if results else 0
        print "median = %dms, avg = %dms, std_dev = %dms" % (median, avg, std_dev)
        store_result_in_db_func([test_name, median, std_dev, size, len(results)])

    comp.run_cmd_on_server(nodes, 'pkill server')

    # if "sp" in test_name:
    exit(0)

if __name__ == "__main__":
    test_nets_opts = {
        # 'sp_quic_go': {'multipath': False, 'run_client': False, 'log_server': "/dev/null"},
        'mp_quic_go': {'multipath': True, 'run_client': False, 'log_server': "/tmp/log_server_d.log"},
    }
    ranges = {
        "bw_a_up": {"range": [10.0, 10.0], "type": float, "count": 1},  # Mbps
        "bw_a_down": {"range": [10.0, 10.0], "type": float, "count": 1},  # Mbps
        #"loss_a": {"range": [0.1, 2], "type": float, "count": 1},  # %, TODO: Characterise typical losses with LTE
        "delay_ms_a_up": {"range": [10.0, 10.0], "type": float, "count": 1},  # ms
        "delay_ms_a_down": {"range": [10.0, 10.0], "type": float, "count": 1},  # ms
        "bw_b_up": {"range": [0.01, 0.01], "type": float, "count": 1},  # Mbps
        "bw_b_down": {"range": [50.0, 50.0], "type": float, "count": 1},  # Mbps
        # "loss_b": {"range": [0.01, 1], "type": float, "count": 1},  # %
        "delay_ms_b_up": {"range": [1000, 1000], "type": float, "count": 1},  # ms
        "delay_ms_b_down": {"range": [10, 10.0], "type": float, "count": 1},  # ms
    }
    additional_columns = [('test_name', str), ('elapsed_time', float), ('std_dev_time', float), ('file_size', int), ('num_xps', int)]
    xp_kwargs = {'file_sizes': (10000000,)}

    run_experimental_design(test_nets_opts, ranges, run_quic_go_xp,
                            db_filename='results_quic_go_specific.db',
                            additional_columns=additional_columns,
                            get_path_cfgs_func=get_path_cfgs_asym_func,
                            xp_kwargs=xp_kwargs)
