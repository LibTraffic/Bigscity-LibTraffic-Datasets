import numpy as np
import pandas as pd
import datetime
import json
import pickle
import util
import sys


dataurl, outputdir, prefix = 'input/GSNetNYC', 'output/GSNetNYC', 'output/GSNetNYC/GSNetNYC'
util.ensure_dir(dataurl)
util.ensure_dir(outputdir)


row_count, column_count = 20, 20
graph_node_count = 243
dyna_count = 3504000


geo_columns = ['geo_id', 'type', 'coordinates']
rel_columns = ['rel_id', 'type', 'origin_id', 'destination_id', 'road_adj', 'risk_adj', 'poi_adj']
dyna_columns = ['dyna_id', 'type', 'time', 'row_id', 'column_id', 'risk', 'holiday', *[f'poi_type_{i}' for i in range(7)],
            'temperature', *[f'weather_{n}' for n in ['clear', 'cloudy', 'rain', 'snow', 'mist']], 
            'inflow', 'outflow']
grid_columns = ['dyna_id', 'type', 'time', 'row_id', 'column_id', 'risk_mask', 'grid_node_map']

geo_type = 'GraphNode'
rel_type = 'rel'
dyna_type = 'state'
grid_type = 'grid'


def write_geo() -> None:
    # write graph nodes instead of grids
    geo_file = open(prefix + '.geo', 'w')

    geo_file.write(','.join(geo_columns))
    geo_file.write('\n')

    for nid in range(graph_node_count):
        row = [nid, geo_type, []]
        geo_file.write(','.join(map(str, row)))
        geo_file.write('\n')

    geo_file.close()


def write_rel() -> None:
    rel_file = open(prefix + '.rel', 'w')

    rel_file.write(','.join(rel_columns))
    rel_file.write('\n')

    adjs = {}
    for k in ['road_adj', 'risk_adj', 'poi_adj']:
        with open(dataurl + '/nyc/' + k + '.pkl', 'rb') as f:
            adjs[k] = pickle.load(f)

    rel_id = 0
    # orig_id points to the first dimension of the grid
    for i in range(graph_node_count):
        for j in range(graph_node_count):
            row = [
                rel_id,
                rel_type,
                i,
                j,
                1,  # adjs['risk_mask'][i][j],
                adjs['road_adj'][i][j],
                adjs['risk_adj'][i][j],
                adjs['poi_adj'][i][j]
            ]
            rel_file.write(','.join(map(str, row)))
            rel_file.write('\n')

            rel_id += 1

    del adjs
    rel_file.close()


def write_dyna() -> None:
    dyna_file = open(prefix + '.dyna', 'w')

    with open(dataurl + '/nyc/all_data.pkl', 'rb') as f:
        ad = pickle.load(f)

    dyna_file.write(','.join(dyna_columns))
    dyna_file.write('\n')

    dyna_id = 0
    time_slots, num_features, num_cols, num_rows = ad.shape

    for r in range(num_rows):
        for c in range(num_cols):
            for ts in range(time_slots):
                dt = datetime.datetime(2013, 1, 1, 0, 0) + datetime.timedelta(days=ts//24, hours=ts%24)
                dt: str = dt.isoformat() + 'Z'
                curr_row_raw = ad[ts, :, c, r]

                row = [
                        dyna_id,
                        dyna_type,
                        dt,
                        r,
                        c,
                        curr_row_raw[0],
                        curr_row_raw[32],
                        *[curr_row_raw[33+i] for i in range(7)],
                        curr_row_raw[40],
                        *[curr_row_raw[41+i] for i in range(5)],
                        curr_row_raw[46],
                        curr_row_raw[47]
                ]

                for i in range(len(row)):
                    if isinstance(row[i], str):
                        continue
                    elif isinstance(row[i], int):
                        row[i] = repr(row[i])
                    elif isinstance(row[i], float):
                        row[i] = repr(row[i])
                    else:
                        raise TypeError()
                dyna_file.write(','.join(row))
                dyna_file.write('\n')

                dyna_id += 1

                if dyna_id % 16384 == 0:
                    print(f'{dyna_id}/{time_slots * num_cols * num_rows}', file=sys.stderr)

    del ad
    dyna_file.close()


def write_grid():
    # actually effectively a .rel file
    grid_file = open(prefix + '.grid', 'w')

    grid_file.write(','.join(grid_columns))
    grid_file.write('\n')

    maps = {}
    for k in ['risk_mask', 'grid_node_map']:
        with open(dataurl + '/nyc/' + k + '.pkl', 'rb') as f:
            maps[k] = pickle.load(f)

    # avoids overlap with .dyna file
    grid_id = dyna_count
    for i in range(row_count):
        for j in range(column_count):
            row = [
                    grid_id,
                    grid_type,
                    '1970-01-01T00:00:00Z',  # dummy
                    i,
                    j,
                    maps['risk_mask'][i][j],
                    # column first; embeds ndarray of shape (row_count, column_count, graph_node_count)
                    # avoids nightmarish eval()
                    '\"' + ' '.join(map(str, maps['grid_node_map'][j * row_count + i, :].tolist())) + '\"'
            ]
            grid_file.write(','.join(map(str, row)))
            grid_file.write('\n')

            grid_id += 1

    del maps
    grid_file.close()


def write_config() -> None:
    config = {
        'geo': {
            'including_types': geo_type,
            geo_type: {
                'coordinates': 'list',  # TODO
            }
        },
        'rel': {
            'including_types': rel_type,
            rel_type: {
                'risk_mask': 'num',
                'road_adj': 'num',
                'risk_adj': 'num',
                'poi_adj': 'num'
            }
        },
        'dyna': {
            'including_types': dyna_type,
            dyna_type: dict(map(lambda x: (x, 'num'), dyna_columns))
        },
        'grid': {
            'including_types': grid_type,
            grid_type: {
                'row_id': 'num',
                'column_id': 'num',
                'risk_mask': 'num',
                'grid_node_map': 'str'
            }
        },
        'info': {
            'data_col': dyna_columns[5:],
            'data_files': ['GSNetNYC'],
            'graph_input_col': [
                'risk',
                'inflow',
                'outflow'
            ],
            'target_time_col': [
                'holiday'
            ],
            'geo_file': 'GSNetNYC',
            'rel_file': 'GSNetNYC',
            'grid_file': 'GSNetNYC',
            'load_external': True,
            'output_dim': 1,
            'time_intervals': 3600,
            'add_time_in_day': True,
            'add_day_in_week': True,
            'num_of_target_time_feature': 1,
            'calculate_weight_adj': False,
            'len_closeness': 3,
            'len_period': 4,
            'len_trend': 0,
            'interval_period': 7,
            'interval_trend': 0,
            'pad_back_period': 0,
            'pad_forward_period': 0,
            'pad_back_trend': 0,
            'pad_forward_trend': 0,
            'risk_thresholds': [0, 0.04, 0.08],
            'risk_weights': [0.05, 0.2, 0.25, 0.5]
        }
    }

    with open(outputdir + '/config.json', 'w', encoding='UTF-8') as f:
        json.dump(config, f, ensure_ascii=False)


if __name__ == '__main__':
    write_geo()
    write_rel()
    write_dyna()
    write_grid()
    write_config()
