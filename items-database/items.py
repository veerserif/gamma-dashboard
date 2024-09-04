# Import packages
from dash import Dash, html, dcc, callback, Output, Input, State, ctx, no_update, dash_table
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
#import plotly.express as px
import pandas as pd
import re, math, os

# Import data

wpns_df = pd.read_csv('items-database/src/240628_weapons.csv')
wpns_df.rename(columns={'Unnamed: 0':'Weapon ID'}, inplace=True)
# Do stuff here


# Initialize app
app = Dash(external_stylesheets=[dbc.themes.BOOTSTRAP]) #external_stylesheets=[dbc.themes.DARKLY, 'items-database/assets/style.css']

title_section = dbc.NavbarSimple( #header
        brand="GAMMA Weapons Spreadsheet",
        brand_href='#',
        color='primary',
        dark=True
        )

wpn_table = html.Div(
    dash_table.DataTable(
        wpns_df.to_dict('records'), 
        [{"name": i, "id": i} for i in wpns_df.columns],
        style_table={'overflowX': 'scroll'}
    )
)


# Layout
app.layout = [
    dbc.Container([
        dbc.Row(dbc.Col(title_section)),
        dbc.Row(dbc.Col(wpn_table))
    ])
]

# Callbacks

# Run the app

if __name__ == '__main__':
    app.run(debug=True)