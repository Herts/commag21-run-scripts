"""Custom topology example

Two directly connected switches plus a host for each switch:

   host --- switch --- switch --- host

Adding the 'topos' dict with a key/value pair to generate our newly defined
topology enables one to pass in '--topo=mytopo' from the command line.
"""
import argparse
import datetime
import os
import sqlite3
import time

import comp

class TypeWrapper(object):
    def __init__(self, type_builtin, name):
        self.builtin = type_builtin
        self.name = name

    def __call__(self, *args, **kwargs):
        return self.builtin(*args, **kwargs)

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


int = TypeWrapper(int, "INTEGER")
float = TypeWrapper(float, "REAL")
str = TypeWrapper(str, "TEXT")


def load_wsp(filename, nrows, ncols):
    # Open the file
    f = open("%s" % filename)
    lines = f.readlines()
    f.close()

    # The interesting line is the third one
    line = lines[2]
    split_line = line.split(",")
    nums = []

    for x in split_line:
        nums.append(float(x))
    print(len(split_line))
    print(len(nums))

    if len(nums) != nrows*ncols:
        raise Exception("wrong number of elements in wsp matrix: %d instead of %d(with %d rows)" % (len(nums), nrows*ncols, nrows))

    print("load matrix")

    # The matrix is encoded as an array of nrowsxncols
    matrix = []
    for i in range(nrows):
        row = []
        for j in range(ncols):
            try:
                row.append(nums[i * ncols + j])
            except:
                print(i * ncols + j)
                raise

        matrix.append(row)

    return matrix


class ParamsGenerator(object):
    def __init__(self, params_values, matrix):
        self.index = 0
        self.params_values = params_values
        for k in ('delay_ms_a', 'delay_ms_b'):
            if isinstance(params_values.get(k, None), list):
                for i in range(len(params_values[k])):
                    params_values["%s_%d" % (k, i)] = params_values[k][i]
                params_values.pop(k, None)
        self.param_names = list(sorted(params_values.keys()))
        self.ranges_full_name = {self._full_name(key, val["count"]): val["range"] for key, val in params_values.items()}
        names = []
        for n in params_values.keys():
            for key in params_values[n]["range"].keys() if isinstance(params_values[n]["range"], dict) else [None]:
                names.append((n, key))
        self.param_full_names = sorted(flatten(map(lambda name_key: [self._full_name(name_key[0], i, name_key[1]) for i in range(params_values[name_key[0]]["count"])], names)))
        # decide for an arbitrary ordering of the parameters
        print self.param_full_names
        self.params_indexes = {self.param_full_names[i]: i for i in range(len(self.param_full_names))}
        self.matrix = matrix

    def _full_name(self, name, count, key=None):
        if self.params_values[name]["count"] > 1:
            return "%s_%d%s" % (name, count, ("_%s" % str(key)) if key is not None else "")
        return "%s%s" % (name, ("_%s" % str(key)) if key is not None else "")

    def generate_value(self):
        retval = self._generate_value_at(self.index)
        self.index += 1
        return retval

    def _generate_value_at(self, i):
        retval = {}
        for name in self.param_names:
            retval[name] = []
            for count in range(self.params_values[name]["count"]):
                param_range = self.params_values[name]["range"]
                if isinstance(param_range, dict):
                    to_append = {key: self.params_values[name]["type"](
                              self.matrix[self.params_indexes[self._full_name(name, count, key)]][i] * (param_range[key][1] - param_range[key][0]) + param_range[key][0])
                        for key in param_range.keys()}
                else:
                    full_name = self._full_name(name, count)
                    param_index = self.params_indexes[full_name]
                    float_value = self.matrix[param_index][i]
                    to_append = self.params_values[name]["type"](float_value * (param_range[1] - param_range[0]) + param_range[0])
                retval[name].append(to_append)
        return retval

    def __len__(self):
        return len(self.matrix[0])

    def generate_all_values(self):
        for i in range(len(self.matrix[0])):
            yield self._generate_value_at(i)

    def generate_sql_create_table(self, additional_values):
        lines = []
        for name in self.param_names:
            for count in range(self.params_values[name]["count"]):
                if isinstance(self.params_values[name]["range"], dict):
                    for k in sorted(self.params_values[name]["range"].keys()):
                        lines.append("%s %s NOT NULL" % (self._full_name(name, count, k),
                                                         str(self.params_values[name]["type"])))
                else:
                    lines.append("%s %s NOT NULL" % (self._full_name(name, count), str(self.params_values[name]["type"])))

        for name, type in additional_values:
            lines.append("%s %s NOT NULL" % (name, str(type)))

        return """
        CREATE TABLE IF NOT EXISTS results (
          %s
        );
        """ % (',\n'.join(lines))

    @staticmethod
    def generate_sql_insert(vals):
        retval = []
        for v in vals:
            if isinstance(v, dict):
                retval += [str(v[k]) for k in sorted(v.keys())]
            else:
                retval.append("'%s'" % str(v))
        print """ INSERT INTO results VALUES (%s); """ % ", ".join(retval)
        return """ INSERT INTO results VALUES (%s); """ % ", ".join(retval)


def flatten(l):
    """
        inefficiently flattens a list
        l: an arbitrary list
    """
    if not l:
        return list(l)
    if isinstance(l[0], (list, tuple)):
        return flatten(l[0]) + flatten(l[1:])
    return [l[0]] + flatten(l[1:])


def generate_random_files(file_sizes):
    """
        Generates random files according to the given sizes.
        The files will be placed in the current directory with a filename of the form `random_%d` % size
    """
    for s in file_sizes:
        with open('random_%d' % s, 'wb') as f:
            f.write(os.urandom(s))


def get_path_cfgs_default_func(v, **kwargs):
    mqs_1 = int(1.5 * (((v['bw_a'] * 1000000) / 8)) * (2 * v['delay_ms_a'] / 1000.0))  # 1.5 * BDP, TODO: This assumes that packet size is 1200 bytes
    path_1_cfg = {"bw": v["bw_a"], "delay": v["delay_ms_a"], "max_queue_size": mqs_1}
    to_return = {'path_1_cfg': path_1_cfg}
    if 'bw_b' in v and 'delay_ms_b' in v:
        mqs_2 = int(1.5 * (((v['bw_b'] * 1000000) / 8)) * (2 * v['delay_ms_b'] / 1000.0))  # 1.5 * BDP, TODO: This assumes that packet size is 1200 bytes
        path_2_cfg = {"bw": v["bw_b"], "delay": v["delay_ms_b"], "max_queue_size": mqs_2}
        to_return['path_2_cfg'] = path_2_cfg
    
    return to_return


def run_experimental_design(test_nets_opts, ranges, run_xp_func,
                            wsp_filename="wsp_owd_8_mp", wsp_rows=8, wsp_cols=139,
                            db_filename='results.db',
                            additional_columns=[],
                            start_func=None,
                            topology_func=None,
                            get_path_cfgs_func=get_path_cfgs_default_func,
                            max_runs=None,
                            xp_kwargs={}):
    from os import sys, path
    dir_path = path.dirname(path.abspath(__file__))
    sys.path.append(dir_path)

    if start_func:
        start_func(**xp_kwargs)

    filename = os.path.join(dir_path, wsp_filename)
    matrix = load_wsp(filename, wsp_rows, wsp_cols)
    gen = ParamsGenerator(ranges, matrix)
    vals = gen.generate_all_values()
    # vals = generate_variance_tests(ranges)

    conn = sqlite3.connect(os.path.join(dir_path, db_filename))
    cursor = conn.cursor()
    sql_create_table = gen.generate_sql_create_table(additional_values=additional_columns)
    print sql_create_table
    cursor.execute(sql_create_table)
    conn.commit()

    for i, v in enumerate(list(vals)[0:]):
        if max_runs and i >= max_runs:
            return

        for key, value in v.items():
            if isinstance(value, list):
                v[key] = value[0]

        if topology_func:
            topology_func(v, **xp_kwargs)

        for test_name, setup_nets_opts in test_nets_opts.iteritems():
            print "net config == " + str(setup_nets_opts)
            print "v == " + str(v)

            path_cfgs = get_path_cfgs_func(v, exp_index=i, **xp_kwargs)
            nodes = comp.get_comp_nodes(**path_cfgs)

            def store_result_in_db_func(result_array):
                # ugly way to handle failed results...
                values_list = flatten([v[k] for k in sorted(v.keys())]) + result_array
                sql_values_list = gen.generate_sql_insert(values_list)
                print sql_values_list
                cursor.execute(sql_values_list)
                conn.commit()
                print "committed"

            print "experiment %d/%d" % (i + 1, len(gen))
            run_xp_func(nodes, test_name, setup_nets_opts, store_result_in_db_func, **xp_kwargs)
