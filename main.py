#%%
import requests
import zipfile
import io

import geopandas as gpd
import pandas as pd
import numpy as np
import json

import imageio
from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap
#%%
get_geo_date = True
get_covid_data = True
#%%
### extract the geodata data of belgium
zip_file_url = 'https://statbel.fgov.be/sites/default/files/files/opendata/Statistische%20sectoren/sh_statbel_statistical_sectors_31370_20200101.geojson.zip'
r = requests.get(zip_file_url)
z = zipfile.ZipFile(io.BytesIO(r.content))
z.extractall()
#%%
## manipule the geo file to get regions borders and municipalities centers
if get_geo_date==True:
    file_path = 'sh_statbel_statistical_sectors_20200101.geojson/sh_statbel_statistical_sectors_20200101.geojson'
    be_geo_data = gpd.read_file(file_path)

    ## get municipalities
    be_geo_data_nis = be_geo_data[['cd_munty_refnis', 'geometry']]
    be_geo_data_nis = be_geo_data.dissolve(by='cd_munty_refnis')
    be_geo_data_nis.to_file('sh_statbel_statistical_nis.geojson', driver='GeoJSON')

    ## get regions
    be_geo_data_rgn = be_geo_data[['tx_rgn_descr_fr', 'geometry']]
    be_geo_data_rgn = be_geo_data_rgn.dissolve(by='tx_rgn_descr_fr')
    be_geo_data_rgn.to_file('sh_statbel_statistical_rgn.geojson', driver='GeoJSON')
else:
    be_geo_data_nis = gpd.read_file('sh_statbel_statistical_nis.geojson')
    be_geo_data_rgn = gpd.read_file('sh_statbel_statistical_rgn.geojson')
#%%
## manipulate the daily covid data to get daily cases per municipality
if get_covid_data == True:
    data_url = "https://epistat.sciensano.be/Data/COVID19BE_CASES_MUNI.json"
    r = requests.get(data_url)
    json_data = r.json()
    ## transform to dataframe
    covid_data_pd = pd.DataFrame.from_records(json_data)
    covid_data_pd = covid_data_pd.rename(columns={'NIS5' : 'cd_munty_refnis'})
    covid_data_pd = covid_data_pd[['cd_munty_refnis', 'CASES', 'DATE']]
    covid_data_pd = covid_data_pd.dropna()

    ## get all different municipalities
    all_cities_df = pd.DataFrame()
    all_cities_df['cd_munty_refnis'] = pd.Series(covid_data_pd['cd_munty_refnis'].unique())
    all_cities_df['merge_key'] = 1

    ## get all different dates
    all_dates_df = pd.DataFrame()
    all_dates_df['DATE'] = pd.Series(covid_data_pd['DATE'].unique())
    all_dates_df['merge_key'] = 1

    ## merge all dates municipalities to have all combinations of both
    covid_data_pd_full = pd.merge(all_dates_df, all_cities_df, left_on='merge_key', right_on='merge_key', how='left')
    covid_data_pd_full = pd.merge(covid_data_pd_full, covid_data_pd, on=['DATE', 'cd_munty_refnis'], how='left')
    covid_data_pd_full = covid_data_pd_full.drop('merge_key', axis=1)
    ## set nb cases to 0 when missing
    covid_data_pd_full['CASES'] = covid_data_pd_full['CASES'].fillna(0)
    covid_data_pd_full['cd_munty_refnis'] = covid_data_pd_full['cd_munty_refnis'].astype(str)
    be_geo_data_nis = be_geo_data_nis.reset_index(drop=True)
    be_geo_data_nis['cd_munty_refnis'] = be_geo_data_nis['cd_munty_refnis'].astype(str)

    ## save centroid and not polygons
    be_geo_data_nis['centroid'] = be_geo_data_nis.centroid
    be_geo_data_nis = be_geo_data_nis[['cd_munty_refnis', 'centroid']]
    be_geo_data_nis_covid = pd.merge(covid_data_pd_full, be_geo_data_nis, left_on='cd_munty_refnis', right_on='cd_munty_refnis', how='left')
    be_geo_data_nis_covid.to_csv('be_geo_data_nis_covid.csv', index=False)

#%%
## get the saved pandas and transform it to geopandas
be_geo_data_nis_covid = pd.read_csv('be_geo_data_nis_covid.csv')
be_geo_data_nis_covid = be_geo_data_nis_covid.dropna()
be_geo_data_nis_covid['centroid'] = gpd.GeoSeries.from_wkt(be_geo_data_nis_covid['centroid'])
be_geo_data_nis_covid_gpd = gpd.GeoDataFrame(be_geo_data_nis_covid, geometry='centroid')
## transform <5 into mean = 2.5
be_geo_data_nis_covid_gpd['CASES'] = be_geo_data_nis_covid_gpd['CASES'].str.replace('<5', '2.5').astype(float)

#%%
## use a moving average of 7 days to decrease the volatility
mavg_df = be_geo_data_nis_covid_gpd.groupby('cd_munty_refnis')['CASES'].rolling(7).mean()
mavg_df.reset_index(0, drop=True, inplace=True)
mavg_df = mavg_df.rename('CASES_mavg')
be_geo_data_nis_covid_gpd = pd.concat([be_geo_data_nis_covid_gpd, mavg_df], axis=1)
be_geo_data_nis_covid_gpd['CASES_mavg'] = be_geo_data_nis_covid_gpd['CASES_mavg'].fillna(0)

#%%
## get the list of unique dates
date_list = [date for date in be_geo_data_nis_covid_gpd['DATE'].unique()]
#%%
def create_plot_by_date(be_geo_data_rgn, be_geo_data_nis_covid_gpd, selected_date, mvg_avg=True):
    '''
    Description: creates plot per date

    Input: 
    - be_geo_data_rgn: geopandas table with borders per region
    - be_geo_data_nis_covid_gpd: geopandas table with number of cases in each centroid per date
    - selected_date: date to plot

    Optional: 
    - mvg_avg: if use moving average or not

    Returns:
    - image with the plot for the selected date
    '''
    ## custom pastel colors to use for the markers
    cmap = ListedColormap(['#ffd6d6', '#c0ffb6', '#faffb0', '#d0ddff', '#e1bfff'])
    ## select the date
    be_geo_data_nis_covid_gpd_selected_date = be_geo_data_nis_covid_gpd[be_geo_data_nis_covid_gpd['DATE'] == selected_date]
    if mvg_avg == True:
        makersize = be_geo_data_nis_covid_gpd_selected_date['CASES_mavg'].astype(float).values**2
    else:
        makersize = be_geo_data_nis_covid_gpd_selected_date['CASES'].astype(float).values**2

    #create the plot
    fig, ax = plt.subplots(figsize=(15,15))
    ax.axis('off')
    ## plot the region border
    be_geo_data_rgn.plot(ax=ax, color='white', edgecolor='#858693')
    ## plot the dots
    be_geo_data_nis_covid_gpd_selected_date.plot(ax=ax, markersize=makersize, cmap=cmap)
    ## add the date on top
    plt.text(x=0.38, y=1.02, s=selected_date, fontsize=40, transform=ax.transAxes, color='#d3bf91')
    ## transform figure into image and return 
    fig.canvas.draw()
    image = np.frombuffer(fig.canvas.tostring_rgb(), dtype='uint8')
    image = image.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    ## make sure to clear your memory
    plt.close(fig)
    fig.clear(True)
    return image
#%%
## create gif for all dates
max_images = len(date_list)
df = be_geo_data_nis_covid_gpd
imageio.mimsave(f'./{max_images}_days_of_covid.gif', [create_plot_by_date(be_geo_data_rgn, df, i) for i in date_list[:max_images]], fps=5)