# 432 Days of Covid
The goal of this small project was to create an animated gif showing the evolution of the covid pandemic in Belgium the last 432 days.
The circle represent the number of daily covid cases in each municipality of the country.

## Data
I used 2 sources of data:
1. the number of daily cases per municipality given by sciensano.
2. a geodata file with geographical data of belgium found here: statbel.fgov.be

## Packages
I have mainly used geopandas for handling the geographical data and Matplotlib to create the plots. The animated gif has been created using imageio.

