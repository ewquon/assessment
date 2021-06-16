#!/usr/bin/env python
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd

def read_masscec_lidar(fpath,
                       speed_dir_sheet='WLS7-436SpeedDirection',
                       vert_sheet='Sigma-W',
                       avail_sheet='AV',
                      ):
    
    speed_dir = pd.read_excel(fpath, sheet_name=speed_dir_sheet, header=1)
    speed_dir = speed_dir.drop(columns=[col for col in speed_dir.columns
                                        if str(col).startswith('Decimal Day')])
    speed_dir['Date&Time'] = pd.to_datetime(speed_dir['Date&Time'])
    speed_dir.set_index('Date&Time', inplace=True)
    # note: duplicate columns get a ".1" suffix
    # note: speed columns come first, then direction
    newcolumns = [('wdir',float(str(col)[:-2]))
                  if str(col).endswith('.1') else ('wspd',float(col))
                  for col in speed_dir.columns]
    speed_dir.columns = pd.MultiIndex.from_tuples(newcolumns, names=[None,'height'])
    speed_dir = speed_dir.stack(dropna=False)
    
    vert = pd.read_excel(fpath, sheet_name=vert_sheet, header=1)
    vert = vert.drop(columns=[col for col in vert.columns
                              if str(col).startswith('Decimal Day')])
    vert['Date&Time'] = pd.to_datetime(vert['Date&Time'])
    vert.set_index('Date&Time',inplace=True)
    # note: duplicate columns get a ".1" suffix
    # note: speed columns come first, then direction
    newcolumns = [('sigma_w',float(str(col)[:-2]))
                  if str(col).endswith('.1') else ('w',float(col))
                  for col in vert.columns]
    vert.columns = pd.MultiIndex.from_tuples(newcolumns, names=[None,'height'])
    vert = vert.stack(dropna=False)
    
    avail = pd.read_excel(fpath, sheet_name=avail_sheet, header=0)
    avail = avail.drop(columns=['Decimal Day of Year'])
    avail['Date&Time'] = pd.to_datetime(avail['Date&Time'])
    avail.set_index('Date&Time', inplace=True)
    avail = avail.stack(dropna=False)
    avail.name = 'avail'
    
    lidar = pd.concat([speed_dir,vert,avail], axis='columns')
    lidar.index.rename('datetime', level=0, inplace=True)
    
    return lidar

def read_masscec_tower(fpath, tower_sheet='Tower'):
    tower = pd.read_excel(fpath, sheet_name=tower_sheet, header=1)
    tower = tower.drop(columns=[
        'Decimal Day of Year','Decimal Day of Year (logger)','Month','Day ','Hour','Minute','Second'
    ])
    tower['Date & Time'] = pd.to_datetime(tower['Date & Time'])
    tower.set_index('Date & Time',inplace=True)
    tower.index.rename('datetime',inplace=True)
    return tower

#==============================================================================
if __name__ == '__main__':
    import sys
    try:
        xlsxpath = sys.argv[1]
    except IndexError:
        sys.exit(f'USAGE: {sys.argv[0]} xlsx_path [output_name]')
    try:
        datasetname = sys.argv[2]
    except IndexError:
        import os
        fname = os.path.split(xlsxpath)[1]
        fname = os.path.splitext(fname)[0]
        datasetname = fname.split('TimeSeries')[1]
        
    lidar = read_masscec_lidar(xlsxpath)
    lidarfile = f'ASIT_lidar_{datasetname}.csv'
    lidar.to_csv(lidarfile)
    print('wrote',lidarfile)
    
    tower = read_masscec_tower(xlsxpath)
    towerfile = f'ASIT_tower_{datasetname}.csv'
    tower.to_csv(towerfile)
    print('wrote',towerfile)
