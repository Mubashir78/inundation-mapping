import glob
from os.path import join

import geopandas as gpd
import numpy as np
import pandas as pd


# *********************************************************
runoff_clusters_path = "/home/rdp-user/outputs/roughness_optz_v3/outputs/optz_analysis/runoff_clusters/recurrence_flows_nwm_v3_CONUS_100_interval_added_clusters.csv"              
pre_clip_huc8_path = "/efs-drives/fim-dev-efs/fim-data/inputs/pre_clip_huc8/20251209/"
analysis_dir = "/home/rdp-user/outputs/roughness_optz_v3/outputs/optz_analysis/"

# nwm_runoff_efficiency_clusters
runoff_clusters_df = pd.read_csv(runoff_clusters_path)
runoff_clusters_df = runoff_clusters_df.copy()
runoff_clusters_df = runoff_clusters_df[['feature_id', 'runoff_cluster_idx']]

# Calculating avegare roughness values for each sites per cluster
for site in ['ahps', 'ble']: # 

    site_dir = join(analysis_dir, site)
    pattern = "optz_iteration_metrics_" + "*.csv"  # Match all csv files
    optz_paths = glob.glob(join(site_dir, pattern))

    indx=range(len(optz_paths))
    optz_roughness_df = pd.DataFrame(index = indx, 
        columns =['huc', 'lid#', 'lid_mag#', 'min_loss', 'channel_n', 'overbank_n', 'channel_n_1p', 'overbank_n_1p'])
    i = 0
    for optz_csv in optz_paths:

        optz_huc_df = pd.read_csv(optz_csv, dtype={'huc': str})
        optz_huc_df_process = optz_huc_df[['huc', 'nws_lid', 'magnitude', 'iteration', 'total_loss', 'mannN_ch_coef', 'mannN_ob_coef', 'mannN_ch', 'mannN_ob']]
                
        # Find the number of lids (sites) and magnitudes
        if site == 'ahps':
            lid_mag = optz_huc_df_process[optz_huc_df_process['iteration'] == 0]['nws_lid']
            lid_mag_num = len(lid_mag)
            lid_num = len(lid_mag.drop_duplicates(keep='first'))
        else:
            lid_mag_num = 2
            lid_num = 1
        
        optz_huc_dd_df = optz_huc_df_process.drop_duplicates(subset=['iteration'], keep='first')
        optz_huc_dd_df.reset_index(inplace=True)
        cols = ['mannN_ch', 'mannN_ob']
        optz_huc_dd_df = optz_huc_dd_df.copy()
        optz_huc_dd_df[cols] = optz_huc_dd_df[cols].astype(float).round(4)

        # Find the minimum loss
        min_loss = min(optz_huc_dd_df['total_loss'])
        optz_rows_df = optz_huc_dd_df[optz_huc_dd_df['total_loss'] == min_loss]
        optz_ch_n = np.mean(optz_rows_df['mannN_ch']).round(4)
        optz_ob_n = np.mean(optz_rows_df['mannN_ob']).round(4)

        # Find the minimum 1 percentile loss
        min_loss_1perc = min_loss * 1.01
        optz_1perc_df = optz_huc_dd_df[optz_huc_dd_df['total_loss'] <= min_loss_1perc]
        optz_1perc_dd_df = optz_1perc_df.drop_duplicates(subset=['mannN_ch'], keep='first')
        optz_1perc_dd_df.reset_index(inplace=True)
        optz_ch_n_1p = np.mean(optz_1perc_dd_df['mannN_ch']).round(4)
        optz_ob_n_1p = np.mean(optz_1perc_dd_df['mannN_ob']).round(4)

        huc = str(optz_huc_df['huc'][0])
        huc = huc.zfill(8)
        optz_roughness_df.loc[i, "huc"] = huc
        optz_roughness_df.loc[i, "lid#"] = lid_num
        optz_roughness_df.loc[i, "lid_mag#"] = lid_mag_num
        optz_roughness_df.loc[i, "min_loss"] = min_loss
        optz_roughness_df.loc[i, "channel_n"] = optz_ch_n
        optz_roughness_df.loc[i, "overbank_n"] = optz_ob_n
        optz_roughness_df.loc[i, "channel_n_1p"] = optz_ch_n_1p
        optz_roughness_df.loc[i, "overbank_n_1p"] = optz_ob_n_1p

        i = i+1
    optz_roughness_df.to_csv(join(analysis_dir,f'optz_roughness_huc_{site}.csv'), index=False)
    
    nwm_streams_hucs_df = pd.DataFrame(columns =['huc', 'feature_id', 'order_'])
    for huc in optz_roughness_df['huc']: #[0:10]
        nwm_streams_huc8_path = join(pre_clip_huc8_path, huc, 'nwm_subset_streams.gpkg')
        nwm_streams = gpd.read_file(nwm_streams_huc8_path, engine="fiona")
        nwm_streams = nwm_streams.copy()
        nwm_streams = nwm_streams[['ID', 'order_']]
        nwm_streams['huc'] = huc
        nwm_streams.rename(columns={'ID': 'feature_id'}, inplace = True)
        nwm_streams_hucs_df = pd.concat([nwm_streams_hucs_df, nwm_streams], axis = 0, ignore_index=True)

    # merge with nwm_streams
    optz_roughness_df = optz_roughness_df.copy()
    optz_roughness_huc_fid_df = optz_roughness_df.merge(nwm_streams_hucs_df, on="huc", how="inner")

    # merge with nwm_runoff_efficiency_clusters
    optz_roughness_huc_fid_cluster_df = optz_roughness_huc_fid_df.merge(
        runoff_clusters_df, on="feature_id", how="left")
    optz_roughness_huc_fid_cluster_df['runoff_cluster_idx'] = optz_roughness_huc_fid_cluster_df['runoff_cluster_idx'].astype('Int64')
    optz_roughness_huc_fid_cluster_df.to_csv(join(analysis_dir, f'optz_roughness_huc_fid_cluster_{site}.csv'))

    # average roughness by cluster
    avg_optz_roughness_cluster_df = optz_roughness_huc_fid_cluster_df.groupby(
        "runoff_cluster_idx")['channel_n', 'overbank_n', 'channel_n_1p', 'overbank_n_1p'].mean() # group by huc and clusters
        
    # calculating number of lids in each cluster
    huc_cluster_sites_df = optz_roughness_huc_fid_cluster_df[['huc', 'runoff_cluster_idx', 'lid#', 'lid_mag#']]
    huc_cluster_sites_df = huc_cluster_sites_df.drop_duplicates(subset=['huc'], keep='first')
    huc_cluster_sites_df.reset_index(inplace=True)
    cluster_sites_df = huc_cluster_sites_df.groupby("runoff_cluster_idx")['lid#', 'lid_mag#'].sum()
    
    avg_optz_roughness_cluster_sites_df = pd.concat([avg_optz_roughness_cluster_df, cluster_sites_df], axis=1)
    avg_optz_roughness_cluster_sites_df.reset_index(inplace=True)
    avg_optz_roughness_cluster_sites_df.to_csv(join(analysis_dir, f'optz_roughness_cluster_sites_{site}.csv'))

    # changing the runoff clusters by merging them
    optz_roughness_huc_fid_cluster_df['cluster_indx_3'] = optz_roughness_huc_fid_cluster_df["runoff_cluster_idx"]
    optz_roughness_huc_fid_cluster_df['cluster_indx_5'] = optz_roughness_huc_fid_cluster_df["runoff_cluster_idx"]

    mask3 = optz_roughness_huc_fid_cluster_df["runoff_cluster_idx"].isin([2, 3, 4])
    optz_roughness_huc_fid_cluster_df.loc[mask3, 'cluster_indx_3'] = 3
    mask5 = optz_roughness_huc_fid_cluster_df["runoff_cluster_idx"].isin([1, 2, 3, 4, 5])
    optz_roughness_huc_fid_cluster_df.loc[mask5, 'cluster_indx_5'] = 5

    avg_optz_roughness_3clusters_merg_df = optz_roughness_huc_fid_cluster_df.groupby(
        "cluster_indx_3")['channel_n', 'overbank_n', 'channel_n_1p', 'overbank_n_1p'].mean()
    avg_optz_roughness_3clusters_merg_df.to_csv(join(analysis_dir, f'optz_roughness_3clustersMerged_{site}.csv'))

    avg_optz_roughness_5clusters_merg_df = optz_roughness_huc_fid_cluster_df.groupby(
        "cluster_indx_5")['channel_n', 'overbank_n', 'channel_n_1p', 'overbank_n_1p'].mean()
    avg_optz_roughness_5clusters_merg_df.to_csv(join(analysis_dir, f'optz_roughness_5clustersMerged_{site}.csv'))





# ---------------------------------------------------------------------------------
# Create optz_global_mannings
mannings_path = '/efs-drives/fim-dev-efs/fim-data/inputs/rating_curve/variable_roughness/' #mannings_global_optz_alleg.csv'
mannings_global_06_12 = pd.read_csv(join(mannings_path, 'mannings_global_06_12.csv'))

# merge with runoff clusters
mannings_global_06_12_clusters_df = mannings_global_06_12.merge(
        runoff_clusters_df, on="feature_id", how="left")

# merge with global nwm_streams
nwm_streams_path = "/efs-drives/fim-dev-efs/fim-data/inputs/nwm_hydrofabric/nwm_flows_20250328.gpkg"
nwm_streams_conus = gpd.read_file(nwm_streams_path, engine="fiona")
nwm_streams_conus = nwm_streams_conus.copy()
nwm_streams_conus = nwm_streams_conus[['ID', 'order_']]
nwm_streams_conus.rename(columns={'ID': 'feature_id'}, inplace = True)

mannings_global_06_12_clusters_nwm_streams_df = mannings_global_06_12_clusters_df.merge(
        nwm_streams_conus, on="feature_id", how="left")
mannings_global_06_12_clusters_nwm_streams_df.drop(
    columns={'channel_n', 'overbank_n'},
    inplace = True
    )
# mannings_global_06_12_clusters_nwm_streams_df["runoff_cluster_idx"] = mannings_global_06_12_clusters_nwm_streams_df["runoff_cluster_idx"].astype('Int64')
# mannings_global_06_12_clusters_nwm_streams_df["order_"] = mannings_global_06_12_clusters_nwm_streams_df["order_"].astype('Int64')

# read optimized roughness based on stream order
optz_roughness_order_path = '/home/rdp-user/outputs/roughness_optz_v3/outputs/optz_analysis/' #mannings_global_optz_alleg.csv'
optz_roughness_order_df = pd.read_csv(join(optz_roughness_order_path, 'optz_roughness_order.csv'))

mannings_global_optz_clusters_nwm_streams_df = mannings_global_06_12_clusters_nwm_streams_df.merge(
        optz_roughness_order_df,
        on=["runoff_cluster_idx", "order_"],
        how="left"
        )
mannings_global_optz_clusters_nwm_streams_df = mannings_global_optz_clusters_nwm_streams_df.fillna(
    {'channel_n': 0.06, 'overbank_n': 0.12}
)

# ohio river, pittsburg and allegeny custom roughness values
featureIDs_2change_ht = pd.read_csv(join(optz_roughness_order_path,'ohio_allegeny_rivers_fids_mannings_n.csv'))
featureIDs_2change = featureIDs_2change_ht['feature_id'].drop_duplicates(keep='first')

ohio_inchannel_n = 0.012
ohio_overbank_n = 0.0482

featureIDs_2change_df = featureIDs_2change.copy().reset_index()
featureIDs_2change_df['channel_n'] = ohio_inchannel_n
featureIDs_2change_df['overbank_n'] = ohio_overbank_n
featureIDs_2change_df.drop(columns=['index'], inplace=True)

cols_to_update = ['channel_n', 'overbank_n']

mannings_global_optz_clusters_nwm_streams_df = mannings_global_optz_clusters_nwm_streams_df.set_index('feature_id')
featureIDs_2change_df = featureIDs_2change_df.set_index('feature_id')

# this will replace CN and ON in df1 wherever the ID exists in df2
mannings_global_optz_clusters_nwm_streams_df.update(featureIDs_2change_df[cols_to_update])  # only CN and ON are taken from df2

mannings_global_optz_clusters_nwm_streams_df = mannings_global_optz_clusters_nwm_streams_df.reset_index()
featureIDs_2change_df = featureIDs_2change_df.reset_index()
# global_manning_df[global_manning_df["feature_id"].isin(featureIDs_2change_df["feature_id"])]
mannings_global_optz_clusters_nwm_streams_df.to_csv(join(optz_roughness_order_path,'mannings_global_optz_order_cluster_v3f.csv'), index=False)

# create the final csv
mannings_global_optz_df = mannings_global_optz_clusters_nwm_streams_df.drop(columns=['order_', 'runoff_cluster_idx'])
mannings_global_optz_df.to_csv(join(optz_roughness_order_path,'mannings_global_optz_v3f.csv'), index=False)

mannings_global_optz_clusters_nwm_streams_df[mannings_global_optz_clusters_nwm_streams_df['feature_id'] == 10109577]

