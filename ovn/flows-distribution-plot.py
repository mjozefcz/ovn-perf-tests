#!/usr/bin/python3

import argparse
import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import os
import re
from itertools import cycle

colors = cycle('bgrcmk')

def collect_series(dir):
    all_data = []
    for file_name in os.listdir(dir):
        if not file_name.endswith('txt'):
            continue
        with open('%s/%s' % (dir, file_name), 'r') as f:
            data = f.read().splitlines()
            data_dict = {}
            for i in data:
                try:
                    k = i.split(':')[0].strip()
                    v = int(i.split(':')[1].strip())
                    data_dict[k] = v
                except IndexError:
                    pass
            if 'timestamp' not in data_dict.keys():
                timestamp = re.search('[0-9]+', file_name)
                if not timestamp:
                    continue
                data_dict['timestamp'] = int(timestamp[0])
        all_data.append({int(timestamp[0]): data_dict})
    data_sorted = sorted(all_data, key=lambda s: list(s.keys())[0])

    series = {}
    for d in data_sorted:
        for k, v in d.items():
            for v1, v2 in v.items():
                current = series.get(v1)
                if current:
                    current.append(v2)
                else:
                    series[v1] = [v2]
    return series


def remote_not_valuable_series(series):
    # for lflow grahs remove series that are not valuable
    # get max value for each serie
    highest_values_map = {}
    for k,v in series.items():
        if k == 'timestamp' or k.startswith('num'):
            continue
        highest_values_map[k] = max(v)
    highest_values_map = sorted(highest_values_map, key=lambda x: x[1])
    # Leave only highest 10 series
    lowest_values_keys = highest_values_map[10:]
    for k in lowest_values_keys:
        series.pop(k)
    return series


def graph(series):
    # tuples correponding to x- and y-values
    graphs = [
        ('time','lflows'),
        ('time', 'num_of_rows'),
        ('num_of_fips', 'lflows'),
        ('num_of_routers', 'lflows')]
    graphs_plots = {}
    for g in graphs:
        fig, ax = plt.subplots()
        ax.set(xlabel=g[0], ylabel=g[1], title='%s vs %s' % (g[0], g[1]))
        ax2 = ax.twinx()
        ax.autoscale(True)
        graphs_plots[g] = (fig, ax, ax2)

    def get_required_graphs(k):
        ret_graphs = {}
        for g in graphs:
            if k.startswith('num'):
                ret_graphs[graphs[1]] = (graphs_plots[graphs[1]])
            else:
                ret_graphs[graphs[0]] = (graphs_plots[graphs[0]])
            if k == 'num_of_fips':
                ret_graphs[graphs[2]] = (graphs_plots[graphs[2]])
            if k == 'num_of_routers':
                ret_graphs[graphs[3]] = (graphs_plots[graphs[3]])
        return ret_graphs

    def insert_vals(k, series, time):
        v = series[k]
        for graph_k, graph_v in get_required_graphs(k).items():
            custom_graph = False
            if graph_k[0] == 'time':
                xes = time
                xes_label = 'time [s]'
            else:
                custom_graph = True
                xes = v
                xes_label = '%s [num]' % graph_k[0]
            color = next(colors)
            if k == 'timestamp':
                continue
            if k in ('num_of_lflows', 'num_of_mac_bindings'):
                k = '%s - SBDB' % k
                graph_v[2].plot(xes, v, label=k, color=color)
                graph_v[2].set_xlabel(xes_label)
            else:
                if not custom_graph:
                    if graph_k[1] == 'num_of_rows':
                        k = '%s - NBDB' % k
                    graph_v[1].plot(xes, v, label=k, color=color)
                    graph_v[1].set_xlabel(xes_label)
                else:
                    for serie_k, serie_v in series.items():
                        if serie_k.startswith('num') or serie_k == 'timestamp':
                            continue
                        color = next(colors)
                        graph_v[1].plot(xes, serie_v, label=serie_k, color=color)
                    graph_v[1].set_xlabel(xes_label)


    ref_timestamp = series['timestamp'][0]
    timestamp_series = series['timestamp']
    ref_timestamp_series = list(
        map(lambda x: x-ref_timestamp, series['timestamp']))
    for s in series:
        insert_vals(s, series, ref_timestamp_series)

    for k, v in graphs_plots.items():
        v[1].set_ylim(ymin=0)
        v[2].set_ylim(ymin=0)
        v[1].set_xlim(xmin=0)
        v[2].set_xlim(xmin=0)

        v[1].legend(loc="upper left")
        if not v[2].lines:
            v[2].remove()
        else:
            v[2].legend(loc="upper right")
    plt.show()


def main():
    parser = argparse.ArgumentParser(description='Graph flows-distribution data')
    parser.add_argument('--dir', required=True, help='dir to load the flows-distribution files')
    args = parser.parse_args()

    if not os.path.isdir(args.dir):
        raise ValueError('Provided directory doesn\'t exit.')
        exit(1)

    series = collect_series(args.dir)
    series = remote_not_valuable_series(series)
    graph(series)


if __name__ == "__main__":
    main()
