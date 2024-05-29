# Import packages
from dash import Dash, html, dcc, callback, Output, Input, State, ctx, no_update
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
#import plotly.express as px
import pandas as pd
import re, math, os

# Incorporate data

weapons_df = pd.read_csv('damage-sim/src/weapons2.csv', index_col = 0)
ammo_df = pd.read_csv('damage-sim/src/ammo.csv', index_col = 0, skiprows=[1,2,3,4,5,6,7,8])
stalkers_df = pd.read_csv('damage-sim/src/curated_npc_profiles.csv', index_col = 0)
mutants_df = pd.read_csv('damage-sim/src/mutants.csv', index_col = 0, skiprows=[1])
ids_df = pd.concat([weapons_df[['name']], ammo_df[['name']], mutants_df[['name']], stalkers_df[['name']]])

#Other important data
difficulty_mult = {
    'easy': 1.3,
    'medium': 1.05,
    'hard': 0.9,
    'master': 0.8
}

legmeta = [ #if gun/ammo is in this section, do not add an AP boost to legshots; lines 807-814
    "ammo_7.92x33_ap",
    "ammo_7.92x33_fmj",
    "ammo_7.62x54_7h1",
    "ammo_7.62x54_ap",
    "ammo_7.62x54_7h14",
    "ammo_magnum_300",
    "ammo_50_bmg",
    "ammo_gauss",
    "wpn_l96a1",
    "wpn_mk14",
    "wpn_remington700",
    "wpn_m40_cw",
    "wpn_wa2000"
]

#standardize hitzone input because fuck no
hitzones_mutants = [ "head", "torso", "limbs", "rear", "other"]
hitzones_stalkers = [ "head", "torso", "arms", "legs"]
stalker_bone_mult = { "head": 3.65, "torso": 0.9, "arms": 0.4, "legs": 0.4 }

# # # # # # # # # # # # # # # # # # # # 
# Damage sim functions
# # # # # # # # # # # # # # # # # # # # 

def get_name(some_id): #gets name from namecol if it exists
    return ids_df.loc[some_id].to_list()[0]

def get_id(some_name): #gets name from namecol if it exists
    return ids_df.index[ids_df['name'] == some_name].to_list()[0]

def get_ammo_type(weapon): #returns array of allowable ammos for the weapon
    ammo_array = []
    re_ammo = r'(ammo_\d[.x\d]{1,6})|(ammo_[a-z]{0,6})'
    ammo_class = ""
    if weapon: #if weapon exists
        ammo_class = re.search(re_ammo, weapons_df.loc[weapon]['ammo_type'])
        if ammo_class.group(1) is not None:
            ammo_array = [a for a in ammo_df.index if a.find(ammo_class.group(1)) != -1]
        elif ammo_class.group(2) is not None:
            ammo_array = [a for a in ammo_df.index if a.find(ammo_class.group(2)) != -1]
    return ammo_array
    
def get_wpn_hit_power(weapon): #takes some string that we will match to weapon ID
    wpn_name = str(weapon) # we convert to string
    hit_power = 0.0
    try:
        hit_power = float( weapons_df.loc[wpn_name]['hit_power'] )
    except (TypeError, KeyError):
        print('Error: bad input wpn name')
        return
    return hit_power

def get_ammo_stats(ammo): #we want k_hit, k_ap, air_res, ammo_mult_mutant, ammo_mult_gigant, ammo_mult_stalker, hp_no_pen, pellets
    ammo_name = str(ammo)
    try:
        ammo_s = ammo_df.loc[ammo_name][1:].to_dict()
    except (TypeError, KeyError):
        print('Error: bad input ammo name')
        return
    return ammo_s

def get_npc_stats(npc): #see above but npcs version
    npc_id = str(npc)
    try:
        npc_data = stalkers_df.loc[npc_id][1:].to_dict()
    except (TypeError, KeyError):
        print('Error: bad input stalker profile')
        return
    return npc_data

def get_mutant_stats(mutant): #clone of npc function
    mutant_id = str(mutant)
    try:
        mutant_data = mutants_df.loc[mutant_id][1:].to_dict()
    except (TypeError, KeyError):
        print('Error: bad input mutant profile')
        return
    return mutant_data

def is_wpn_silenced(weapon, silenced=False):
    wpn_name = str(weapon)
    silenced = bool(silenced) #whether or not there's an additional silencer
    if silenced == False:
        try:
            silenced = weapons_df.loc[wpn_name]['integrated_silencer']
            return silenced #always returns True if there's an integrated silencer
        except (TypeError, KeyError):
            print('Bad input, silenced status')
            return
    else:
        return silenced
    
def get_armor(target, hitzone="torso"): #args: target (str), id of mutant/stalker; hitzone, area hit, opt
    armor = 0.0
    bodyzone = [ "torso", "arms", "legs"]
    if target.find('stalker') == -1: #if target is not a stalker
        armor = mutants_df.loc[target]['skin_armor']
        return armor
    elif hitzone in bodyzone: #body shot
        armor = stalkers_df.loc[target]['body_bonearmor']
        return armor
    elif hitzone == "head":
        armor = stalkers_df.loc[target]['head_bonearmor']
        return armor
    else:
        return armor
    return

# Damage sub-functions

def barrel_cond(barrel): #takes a float
    barrel_health = float(barrel)
    barrel_corrected = 0.0
    try:
        barrel_corrected = ( 130 - ( 1.12 * barrel_health ) ) * ( barrel_health * 1.12 ) / 100
        if barrel_corrected < 1:
            return barrel_corrected
        else:
            return 1.0
    except TypeError:
        print('Error: bad barrel cond input')
        return
    return

def stalker_legs_ap(weapon, bullet): #leg-specific AP boosts; only call if target is lowerbody
    buckshot = ["ammo_12x70_buck", "ammo_20x70_buck", "ammo_23x75_shrapnel"]
    base_ap = get_ammo_stats(bullet)['k_ap'] * 10
    final_ap = 0.0
    if bullet in buckshot:
        final_ap = base_ap + 0.013
        return final_ap
    elif (weapon in legmeta) or (bullet in legmeta):
        final_ap = base_ap
        return final_ap
    else:
        final_ap = base_ap + 0.075
        return final_ap
    
def npc_faction_res(faction): #per-faction resistances
    faction_res = {'ap_res': 1.0, 'dmg_res': 1.0 } #isg_res = ap res, sin_res = dmg res
    if faction == "greh":
        faction_res['dmg_res'] = 0.3
        faction_res['ap_res'] = 0.9
    elif faction == "isg":
        faction_res['dmg_res'] = 0.8
        faction_res['ap_res'] = 0.7
    elif faction == "monolith":
        faction_res['dmg_res'] = 0.65
        faction_res['ap_res'] = 0.9
    elif faction == "bandit":
        faction_res['ap_res'] = 1.1
    return faction_res

def get_stalkerhit_ap(input_array):
    # Array parsing
    keys = ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
    input_dict = dict(zip(keys, input_array))
    
    surrendering = False #let's just not deal with surrendering atm
    gbo_dmg = 0.0
    silencer_mult = 1
    ammo = get_ammo_stats(input_dict['bullet'])
    local_ap = ammo['k_ap'] * 10
    difficulty = difficulty_mult[input_dict['game_difficulty']]
    barrel_mult = barrel_cond(input_dict['barrel'])
    hp_no_penetration_penalty = ammo['hp_no_penetration_penalty']
    bone_mult = stalker_bone_mult[input_dict['hitzone']]
    target_d = get_npc_stats(input_dict['target'])
    ap_scale = target_d['ap_scale']
    hit_fraction = target_d['hit_fraction']
    bone_armor = get_armor(input_dict['target'], input_dict['hitzone'])
    faction_res = npc_faction_res(input_dict['faction'])
    
    wpn_hit_power = get_wpn_hit_power(input_dict['weapon'])
    air_res_function = (1 + input_dict['dist'] / 200 * (ammo['air_res'] * 0.5 / (1 - ammo['air_res'] + 0.1 )))
    
    #needed for headshot AP
    buckshot = ["ammo_12x70_buck", "ammo_20x70_buck", "ammo_23x75_shrapnel"]
    
    #Silencer mult handling
    if input_dict['silencer'] == True:
        silencer_mult = 1.07
    elif is_wpn_silenced(input_dict['weapon'], input_dict['silencer']) == True:
        silencer_mult = 1.07
    else:
        silencer_mult = 1
    
    #Hitzone-specific AP changes
    if input_dict['hitzone'] == "legs":
        local_ap = stalker_legs_ap(input_dict['weapon'], input_dict['bullet'])
    if input_dict['hitzone'] == "head":
        if input_dict['bullet'] in buckshot:
            local_ap = local_ap + 0.019
        else:
            local_ap = local_ap + 0.04
    
    local_ap = local_ap * ap_scale * barrel_mult
    local_ap = local_ap / air_res_function * faction_res['ap_res'] * silencer_mult * difficulty * 0.8
    
    return local_ap
    
# Actual damage functions

def mutant_hit(input_array):

    keys = ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
    input_dict = dict(zip(keys, input_array))

    ammo = get_ammo_stats(input_dict['bullet'])
    mutant = get_mutant_stats(input_dict['target'])
    cqc_mult = 1.0 #not handling melee weapons in this version
    mutant_mult = mutant['mutant_mult']
    ammo_mult = ammo['ammo_mult_mutant']
    spec_monster_mult = mutant['spec_mutant_mult']
    crit_mult = 1.0
    bone_mult = 1.0
    gbo_dmg = 0.0
    
    #special pseudogiant handling
    if input_dict['target'] == 'm_gigant_e':
        ammo_mult = ammo['gigant_ammo_mult']
        
    # start deriving calculated values
    raw_dmg = weapons_df.loc[input_dict['weapon']]['hit_power'] * ammo['k_hit'] * ammo['pellets']
    air_res = ammo['air_res']
    difficulty = difficulty_mult[input_dict['game_difficulty']]
    barrel_mult = barrel_cond(input_dict['barrel'])
    bone_mult = mutant[input_dict['hitzone']]
    
    #check for crits
    if mutant['crit_zone'] != "none":
        if mutant['crit_zone'] == input_dict['hitzone']:
            crit_mult = mutant['crit_hit']
            
    bone_mult = bone_mult * crit_mult
    
    #final calculation
    gbo_dmg = raw_dmg / ( 1 + input_dict['dist'] / 200 * ( air_res * 0.5 / ( 1 - air_res + 0.1 ))) * mutant_mult * ammo_mult * spec_monster_mult * bone_mult * cqc_mult * barrel_mult * difficulty
    #bullshit zombie modifier
    gbo_dmg = gbo_dmg * mutant['zombie_modifier']
    return gbo_dmg #, input_dict['bullet'], input_dict['target'], input_dict['hitzone']

def stalker_armor_calc(ap, dmg, bone_armor, hit_fraction, hp_no_penetration_penalty):
    loss_increment = ap * 0.6
    new_bone_armor = bone_armor - loss_increment
    did_shot_pen = False
    if ap < bone_armor:
        if ap > new_bone_armor:
            dmg = dmg * hit_fraction
            return did_shot_pen, new_bone_armor, dmg
        else:
            #remove random number function in favour of min/avg/max
            min_dmg = 0.0025 * dmg * hit_fraction * 25 / hp_no_penetration_penalty
            avg_dmg = 0.0025 * dmg * hit_fraction * 62.5 / hp_no_penetration_penalty
            max_dmg = 0.0025 * dmg * hit_fraction * 100 / hp_no_penetration_penalty
            return did_shot_pen, new_bone_armor, avg_dmg, min_dmg, max_dmg
    if ap > bone_armor:
        did_shot_pen = True
        return did_shot_pen, new_bone_armor, dmg
    
def shots_to_pen(input_array): #how many shots needed to destroy armor at hitzone
    
    # Array parsing
    keys = ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
    input_dict = dict(zip(keys, input_array))
    
    shots_to_pen = 1 # min. shot to penetrate is 1
    ap_scale = 0.75 #anomaly engine default
    if input_dict['target'].find('m_') == -1: #if not mutant. i really should have made this a function.
        ap_scale = stalkers_df.loc[input_dict['target']]['ap_scale']
    elif input_dict['target'].find('stalker_') == -1: #if NOT stalker
        ap_scale = 0.75
    local_ap = get_stalkerhit_ap(input_array)
    bone_armor = get_armor(input_dict['target'], input_dict['hitzone'])
    loss_increment = local_ap * 0.6
    
    if local_ap * ap_scale < bone_armor:
        shots_to_pen = math.ceil(bone_armor - local_ap * ap_scale / loss_increment) # round UP to nearest integer, since 3.1 = needs 4 shots to pen
    if shots_to_pen < 1: #clamp minimum to 1
        shots_to_pen = 1
    return shots_to_pen


def stalker_hit(input_array, bone_armor = None):
    # Array parsing
    keys = ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
    input_dict = dict(zip(keys, input_array))
    
    surrendering = False #let's just not deal with surrendering atm
    gbo_dmg = 0.0
    silencer_mult = 1
    ammo = get_ammo_stats(input_dict['bullet'])
    local_ap = ammo['k_ap'] * 10
    difficulty = difficulty_mult[input_dict['game_difficulty']]
    barrel_mult = barrel_cond(input_dict['barrel'])
    hp_no_penetration_penalty = ammo['hp_no_penetration_penalty']
    bone_mult = stalker_bone_mult[input_dict['hitzone']]
    target_d = get_npc_stats(input_dict['target'])
    ap_scale = target_d['ap_scale']
    hit_fraction = target_d['hit_fraction']
    if bone_armor == None: #allows passing of a new armor value
        bone_armor = get_armor(input_dict['target'], input_dict['hitzone'])
    faction_res = npc_faction_res(input_dict['faction'])
    
    wpn_hit_power = get_wpn_hit_power(input_dict['weapon'])
    air_res_function = (1 + input_dict['dist'] / 200 * (ammo['air_res'] * 0.5 / (1 - ammo['air_res'] + 0.1 )))
    
    local_ap = get_stalkerhit_ap(input_array)
    
    gbo_dmg = wpn_hit_power / air_res_function * ammo['k_hit'] * bone_mult * ap_scale * 1.1 * barrel_mult * faction_res['dmg_res'] * difficulty * ammo['ammo_mult_stalker'] * silencer_mult
    
    post_armor = stalker_armor_calc(local_ap, gbo_dmg, bone_armor, hit_fraction, hp_no_penetration_penalty)
    return post_armor
    
def anomaly_engine_pen(gbo_dmg, bullet, target, hitzone, armor_override=None): #how the engine handles pen or non-pen hits
    ap = ammo_df.loc[bullet]['k_ap'] #* 10
    if armor_override != None: #if armor_override is provided
        armor = armor_override
    else:
        armor = get_armor(target, hitzone)
    hit_fraction = 0.0
    d_hit_power = 0.0
    final_dmg = gbo_dmg
    is_pen = False
    ap_scale = 0.75
    hit_scale = 1.0
    #first, get hit fraction and ap_scale
    if target.find('stalker') == -1: #if not NPC
        hit_fraction = mutants_df.loc[target]['hit_fraction']
        hit_scale = mutants_df.loc[target][hitzone]
    else:
        hit_fraction = stalkers_df.loc[target]['hit_fraction']
        ap_scale = stalkers_df.loc[target]['ap_scale']
        hit_scale = stalker_bone_mult[hitzone]
    d_hit_power = (ap - armor) / (ap * ap_scale)
    if (d_hit_power < hit_fraction):
        d_hit_power = hit_fraction
    elif d_hit_power > 1:
        d_hit_power = 1
    final_dmg = gbo_dmg * d_hit_power * hit_scale
    #print if armor was penetrated
    if ap * ap_scale > armor:
        is_pen = True
    else:
        is_pen = False
    #print('hit_power: ' + str(d_hit_power) + ', hit_scale: ' + str(hit_scale)) #temporary for debugging
    return is_pen, final_dmg

def time_to_kill(input_array):
    # Array parsing
    keys = ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
    input_d = dict(zip(keys, input_array))
    ttk = 1 #integer, shots to kill, always at least 1
    min_ttk = 1
    max_ttk = 1

    if input_d['target'].find('stalker_') != -1: #if target is stalker
        #partially recreate stalker armor calc
        stp = shots_to_pen(input_array)
        hit = stalker_hit(input_array)
        ttk = stp + math.ceil((1.0 - (stp * hit[2])) / stalker_hit(input_array, 0.0)[2])
        if len(hit) > 3: #if random damage is in play
            #print('STP: ' + str(stp) + ', ' + str(hit))
            min_ttk = stp + math.ceil((1.0 - (stp * hit[3])) / stalker_hit(input_array, 0.0)[2])
            max_ttk = stp  + math.ceil((1.0 - (stp * hit[4])) / stalker_hit(input_array, 0.0)[2])
    elif input_d['target'].find('m_') != -1: #if target is mutant
        damage = anomaly_engine_pen(mutant_hit(input_array), input_d['bullet'], input_d['target'], input_d['hitzone'])[1]
        ttk = math.ceil(1/damage)
    return ttk, min_ttk, max_ttk


# Initialize the app

#style = "path/to/stylesheet.css"
app = Dash(external_stylesheets=[dbc.themes.DARKLY, 'damage-sim/assets/style.css'])

# Theming

# Layout of the actual page

#design header here
title_section = dbc.NavbarSimple( #header
        brand="GAMMA Ballistics Damage Simulator", #name changed on request
        brand_href='#',
        color='primary',
        dark=True
        )

intro_section = html.Div([
    dcc.Markdown('''
    This simulates the effect of taking **one shot** at a chosen target, at a specified distance, using a given weapon and ammo combo.
    Developed by veerserif. Last updated 2024-05-28.
    ''')
])

#design input fields here
input_field_type =  html.Div([
    html.P('I am shooting at a...'), 
    html.Div([
        dbc.Button('Stalker', color='primary', id='stalker-button', n_clicks=0),
        dbc.Button('Mutant', color='primary', id='mutant-button', n_clicks=0)
        ], className="d-grid gap-2 col-6 mx-auto" ) #wide "block" buttons
    ])

input_field_weapons = html.Div([
    dbc.Label('Weapon'),
    
    dbc.Select(
        id='weapons-dropdown',
        options=[{'label': x[1], 'value': x[0]} for x in zip(weapons_df.index, weapons_df['name'])]
    ),
    
    dbc.Label('Integrally silenced', id='integral_silencer', style={'display':'none'}),
    dbc.Switch(id='silencer', label='Silenced', value=False),
    dbc.Label(id='barrel-cond-label', children='Barrel condition:'),
    dcc.Slider(0, 100, 1, #min, max, step
        marks={ i: f'{i}%' for i in range(1,100) if i % 10 == 0 },
        value=70,
         id='barrel-condition-slider')
    ])

input_field_ammo = html.Div([
    html.Label(children='Ammo'),
    dbc.Select(
        id='ammo-dropdown',
        options=[{'label': x[1], 'value': x[0]} for x in zip(ammo_df.index, ammo_df['name'])]
        ),
    dbc.Switch(id='ammo-limiter', label='Limit ammo types', value=False),
    dbc.Tooltip(
        'Limits ammo selection to the default ammo types for the selected weapon.',
        target='ammo-limiter'
    )
])

input_field_target = html.Div(children=[
    html.P('Choose a target type', id='target-type-description'),
    html.Div(
        [
            dbc.Select(id='target-type-inputs'),
            html.P('They are in the faction...', id='faction-desc', hidden=True),
            dbc.Select(id='faction-select', options = [
                {'label':'Other', 'value':'other'},
                {'label': 'Sin', 'value': 'greh'},
                {'label': 'UNISG', 'value': 'isg'},
                {'label':'Monolith', 'value':'monolith'},
                {'label':'Bandit', 'value':'bandit'}
                ], value='other', className='dash-bootstrap', style={'display': 'none'}),
            html.P('I hit them in the'),
            dbc.RadioItems(id='hitzone-select')
    ], id='target-div', style={'display': 'none'})
    ])

input_field_distance = html.Div(
    [
    dbc.Label('Target distance is '),
    dbc.Input(
        id='distance-input',
        type='number',
        inputmode = 'numeric',
        min=0, max=300, step=1,
        debounce = True),
    dbc.FormText('Must be a whole number, between 0 and 300')
], id='styled-numeric-input')

input_field_difficulty = html.Div([
    dbc.Label('Game difficulty'),
    dbc.RadioItems(id='game-difficulty-radio',
        options=[
            {'label':'Easy', 'value':'easy'},
            {'label': 'Medium', 'value':'medium'},
            {'label':'Hard', 'value':'hard'},
            {'label':'Master (hidden)', 'value': 'master'}
            ], value='hard', inline=True
    )])

input_display_options = html.Div([
    dbc.Switch(id='scale-output-numbers', label='Scale output numbers', value=True, style={'padding-top':'0.5em'}),
    dbc.Tooltip('Multiplies most numbers by 100 for readability', target='scale-output-numbers'),
    dbc.Switch(id='show-advanced-options', label='Enable armor override', value=False)
])

input_advanced_options = html.Div([
    dbc.Label('Armor override'),
    dbc.Input(
        id='armor-override',
        type='number',
        inputmode='numeric',
        min=0, max=1, step='any',
        debounce=True
    ),
    dbc.FormText('Must be between 0 and 1. Overwrites default armor value for chosen hitzone/profile. Clear if not using!')
], id='advanced-options-div', style={'display': 'inherit'})

#design output cards here

output_cards_1 = html.Div([
    dbc.CardGroup(
        [
            dbc.Card([
                dbc.CardHeader('Chosen weapon info'),
                dbc.CardBody(
                    [
                        html.H6(id='weapon-card-title'),
                        html.P(id='weapon-card-desc')
                    ]
                )
            ]),
            dbc.Card([
                dbc.CardHeader('Ammo info'),
                dbc.CardBody(
                    [
                        html.H6(id='ammo-card-title'),
                        html.P(id='ammo-card-desc')
                    ]
                )
            ])
        ])
])

output_cards_2 = html.Div([
    dbc.CardGroup([
        dbc.Card([
                dbc.CardHeader('Target info'),
                dbc.CardBody(
                    [
                        html.H6('', id='target-card-title'),
                        html.P('', id='target-card-desc')
                    ]
                )
            ]),
        dbc.Card([
            dbc.CardHeader('Game info'),
            dbc.CardBody(
                [
                    html.P(id='game-card-desc')
                ]
            )
        ])
    ])
])

output_damage_info = html.Div([
    dbc.Card(
        [   
            dbc.CardHeader('Final damage output'),
            dbc.CardBody(id='output-div'),
            dbc.CardFooter('This calculator assumes all targets are on full health.')
        ])
])

sim_explanation = dcc.Markdown('''
    ##### What's the point of this?
    Sating my curiosity, practicing Python/Pandas/Dash, providing an easy tool to play around with damage calculations. Source csvs are available [on Github](https://github.com/veerserif/gamma-dashboard/tree/main/damage-sim/src).
                               
    #### Sources
    Unless otherwise stated, assume all files are the version that wins all overwrites in a vanilla GAMMA installation.
    - **Ammunition**: All stats manually obtained by reading `weapon_ammo.ltx` (not making that mistake again)
    - **Weapons**: Mainly scraped from the various weapon config files, as well as some DLTX overwrites for specific weapons (the Winchester, the Steyr, the FN2000). 
        These were then cross-checked against a partly generated, partly manual list of all obtainable weapons in GAMMA. The resulting weapons list contains all weapons can be found normally (through NPC drops, Nimble trades, or kit upgrades).
    - **Mutants**: All stats manually obtained from `gamedata/configs/creatures` mutant `.ltx` files. The relevant stats here are the same as in vanilla Anomaly.
    - **Stalker armor profiles**: This is a *curated selection* (only the most common armor profiles in use) of armor profiles that are used by GAMMA/Dux's Innumerable Character Kit. These were obtaned by checking `damages.ltx`, `model_captures`, and NPC config ltx files. I then counted the most common profiles and renamed/merged a curated list to serve as the source database for NPC armor profiles.
    
    And yes - NPC profiles are provided both by armor type (e.g. Sunrise, LCS, Skat-9) *and* by faction (Monolith being the most common). Faction type has nothing to do with the NPC's actual faction - there are Eco, Freedom, Merc, Monolith models that all use the same "Monolith armor profile".
    
    Damage formulae, some additional multipliers, and hitzone info all came from `grok_bo.script`. The functions here mirror those provided by `grok_bo.script` as well as the [Anomaly damage calculation](https://pastebin.com/raw/spv4YzaZ) (mutant hits only), recreated in Python.
    Other information about ammo and weapon configs was provided by this [ammo editing tutorial](https://discord.com/channels/912320241713958912/967696698065436682/1154289177693802546) by Momopate, and the [Anomaly modding handbook](https://igigog.github.io/anomaly-modding-book/configs/items/weapons/w_(weapon).ltx.html) for weapon configs.
                                                
    #### Assumptions in the simulator
    Assume that **every NPC in the game** has a health value of **1.0**. This is why damage values are rarely ever over 1. Also, there are additional hard-coded multipliers present, most notably in the calculations for AP. These are not reflected in output - read the source script file to learn more.

    - "Hitzone": what every other game calls a hitbox
    - Weapon base value: `hit_power` in the config, the base damage of the weapon. Multiplied by the bullet damage modifier, `k_hit`, for final damage.
    - AP value: AP is a property of the bullet (`k_ap`), which goes through a series of very fucking complicated calculations if you shoot a stalker, and basically no calculations if you shoot a mutant. Damage that does not penetrate a target's armor deals a reduced amount of damage (specifically, it deals `damage * non-penetrating shot damage cap`, or `(k_hit * hit_power) * hit_scale`).
    - Yes, there's air resistance which dictates damage fall-off over distance. No, I forgot to put in max range in this calculator, look *that* one up in a weapon stats spreadsheet coming soon.
    - Yes really, NPC faction influences AP/damage resistance
    - Yeah pseudogiants ARE bullshit but remember, that's because every NPC has the same health value
    - Yes there's a per-ammo damage mult in GBO
    - Only "normal" mutant variants are available (with the exception of the black chimera)
    - All hitzones are abstracted and grouped, especially for mutants.
    For mutants, the "head" means *just* the head hitbox (excluding neck), torso is the average of `spine`, `spine01` and `spine02`, rear is the average of `pelvis` and `tail`, and limbs are all arm and leg hitzones. `other` reflects the default values.
    For stalkers, for the sake of brevity, individual hitzone values have been abstracted down to those presented in the simulator. In `grok_bo.script` you'll see that, for example, upper arms take different amounts of damage to lower arms.
    - Only "normal" bullet types are considered (no bad ammo in GAMMA)
    - Guns with the same name have had `(_suffix)` added by me - for example, `wpn_mp5` and `wpn_mp5_custom` are both called "MP5A3" in the game. Most of the time this doesn't matter for damage calculations since they have the same/similar stats.
    - This simulator **ignores surrendering/wounded state**, which would significantly reduce the TTK/increase damage dealt to stalkers. Stalkers in the wounded/surrendering state take double damage.
                                                      
    #### Imaginary Q&A
    *How do I find out the armor profile of an NPC in the game?*

    Smart way: edit `grok_bo.script` to write this information to console. Around line 690, where the function is getting the target's bone profile, add:
    ```lua
    printf("NPC armor section: %s",npc_armor_section)
    ```
    Save, run the game, shoot an NPC, then check the console - it should be in the shot report, from the *first time* you shoot a given NPC.
                               
    *I shot* something *in the game, and got different numbers!*
                               
    When in doubt, trust the game and not this tool. For stalkers, since the wounded/surrendering state is ignored, expect to kill stalkers *faster* in-game than this tool would suggest.
                               
    *Why does the ammo limiter only work if I toggle it on and off again?*
                               
    Because it's a fancy disguised checkbox, that's just how it works.
                               
    *Why does the ammo limiter not work on the AK-105 "Swamp Thing"?*
                               
    The caliber swap info is not stored in the weapon configs, only the upgrade configs, and I wasn't going to spend an extra week reading those. Just turn the limiter off and pick 5.56mm.
                               
    *Why are zombie/fracture values so scuffed?*
    
    I wish I knew.
''')

#do styling down there
app.layout = [
    dbc.Container([
        dbc.Row(dbc.Col(title_section)),
        dbc.Row(dbc.Col(intro_section)),

        dbc.Row( # main body
            [
                dbc.Col([ #left col - all inputs
                    input_field_type,

                    html.Hr(),
                    html.Div([
                        html.P('I am using...')
                    ]),
                    input_field_weapons,
                    input_field_ammo,

                    html.Hr(),

                    input_field_target,

                    html.Hr(),

                    input_field_distance,
                    input_field_difficulty,
                    input_display_options,
                    input_advanced_options,
                    
                    html.Div([
                        dbc.Button('Calculate', id='submit-button', n_clicks=0)
                    ], className="d-grid gap-2")
            ],  md = 4,
                style={'padding':'1em'}
            ),

            dbc.Col([ 
                #right side, outputs
                dbc.Alert('You have missing or invalid inputs!', 
                        id='missing-input-alert',
                        color = 'warning',
                        is_open=False,
                        duration=3500),
                dbc.Row([
                    dbc.Col([
                        output_cards_1,
                        output_cards_2
                        ])
                ]),
                dbc.Row([dbc.Col([output_damage_info])], style={'padding-top':'0.5em'})
            ], style={'padding':'1em'})
        ]), 

    dbc.Row([dbc.Col([
        html.H3('Boring Explanations For Big Nerds'),
        sim_explanation
    ])], style={'padding-top':'3em'})

    ])
]

# Callbacks (aka. controls)
# Do this _first_ so that it can modify all the other info, _once_
@callback(
        Output('faction-desc', 'hidden'), 
        Output('target-type-inputs', 'options'),
        Output('target-type-inputs', 'value'),
        Output('target-div', 'style'),
        Output('hitzone-select', 'options'), 
        Output('faction-select', 'style'),
        Output('target-type-description', 'children'),
        Input('mutant-button', 'n_clicks'),
        Input('stalker-button', 'n_clicks')
        )

def set_target_select(btn_mutant,btn_stalker):
    if 'mutant-button' == ctx.triggered_id:
        return True, [{'label': x[1], 'value': x[0]} for x in zip(mutants_df.index, mutants_df['name'])], 'm_boar', {'display': 'inherit'}, hitzones_mutants, {'display': 'none'}, 'My target is a...'
    elif 'stalker-button'  == ctx.triggered_id:
        return False, [{'label': x[1], 'value': x[0]} for x in zip(stalkers_df.index, stalkers_df['name'])], 'stalker_sunrise', {'display': 'inherit'}, hitzones_stalkers, {'display': 'inherit'}, "My target is, or is wearing..."
    else:
        raise PreventUpdate
    
#Advanced options callback
@callback(
        Output('advanced-options-div', 'style'),
        Input('show-advanced-options', 'value')
)

def show_advanced_options(show_options):
    if show_options ==  True:
        return {'display':'inherit'}
    else:
        return {'display':'none'}

#Barrel condition label for user
@callback(
    Output('barrel-cond-label', 'children'),
    Input('barrel-condition-slider', 'value')
)

def update_info_strings(barrel):
    return 'Barrel condition: {}%'.format(
        int(barrel)
    )

#Disable silencer toggle if weapon is integrally silenced
@callback(
    Output('silencer', 'disabled'),
    Output('integral_silencer', 'style'),
    Input('weapons-dropdown', 'value'),
    prevent_initial_call = True
)

def disable_silencer_toggle(weapon):
    silenced = is_wpn_silenced(weapon, False)
    if silenced == True:
        return True, {'display':'inherit'}
    else:
        return False,{'display':'none'}

#Limit ammo to type used by weapon
# Default output: [{'label': x[1], 'value': x[0]} for x in zip(ammo_df.index, ammo_df['name'])]
@callback(
    Output('ammo-dropdown', 'options'),
    State('weapons-dropdown', 'value'),
    Input('ammo-limiter', 'value')
)

def limit_ammo_dropdown(weapon, limiter):
    allowable_ammo = []
    if weapon:
        allowable_ammo = get_ammo_type(weapon)
        if "ammo_12x70_buck" in allowable_ammo: #hand code exception for 12ga because lol fucking typo
            allowable_ammo = ["ammo_12x70_buck", "ammo_12x76_zhekan", "ammo_12x76_dart"]
        if limiter == True:
            return [{'label': x[1], 'value': x[0]} for x in zip(allowable_ammo, ammo_df.loc[allowable_ammo]['name'])]
        elif limiter == False:
            return [{'label': x[1], 'value': x[0]} for x in zip(ammo_df.index, ammo_df['name'])]
    else:
        return no_update

# Shows alert message if user clicks "Calculate" while a field is empty
@callback(
    Output('missing-input-alert', 'is_open'),
    inputs=dict( # ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
        #mutant_button = Input('mutant-button', 'n_clicks'),
        #stalker_button = Input('stalker-button', 'n_clicks'),
        submit = Input('submit-button', 'n_clicks'),
        show_override = State('show-advanced-options', 'value'),
        armor_override = State('armor-override', 'value'),
        weapon = State('weapons-dropdown', 'value'),
        bullet = State('ammo-dropdown', 'value'),
        target = State('target-type-inputs', 'value'),
        hitzone = State('hitzone-select', 'value'),
        faction = State('faction-select','value'),
        dist = State('distance-input', 'value'),
        barrel = State('barrel-condition-slider', 'value'),
        game_difficulty = State('game-difficulty-radio', 'value'),
        silencer = State('silencer', 'value')
        ),
    prevent_initial_call=True
)

def missing_inputs(submit, show_override, armor_override, weapon, bullet, target, hitzone, faction, dist, barrel, game_difficulty, silencer):
    show_alert = False
    if None in [weapon, bullet, target, hitzone, faction, dist, barrel, game_difficulty, silencer]:
        show_alert = True
    if show_override == True:
        if armor_override == None:
            show_alert = True
        elif (armor_override > 1) or (armor_override < 0): #if armor override is on but value too large
            show_alert = True
    return show_alert

# Reflect chosen weapon + ammo stats
@callback(
    output= dict(
        weapon_t = Output('weapon-card-title', 'children'),
        weapon_d =Output('weapon-card-desc', 'children'),
        ammo_t = Output('ammo-card-title', 'children'),
        ammo_d =Output('ammo-card-desc', 'children'),
        target_t = Output('target-card-title', 'children'),
        target_d = Output('target-card-desc', 'children'),
        game_d = Output('game-card-desc', 'children')
    ),
    inputs=dict( # ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
        submit = Input('submit-button', 'n_clicks'),
        show_override = State('show-advanced-options', 'value'),
        armor_override = State('armor-override', 'value'),
        scale_display = State('scale-output-numbers', 'value'),
        weapon = State('weapons-dropdown', 'value'),
        bullet = State('ammo-dropdown', 'value'),
        target = State('target-type-inputs', 'value'),
        hitzone = State('hitzone-select', 'value'),
        faction = State('faction-select','value'),
        dist = State('distance-input', 'value'),
        barrel = State('barrel-condition-slider', 'value'),
        game_difficulty = State('game-difficulty-radio', 'value'),
        silencer = State('silencer', 'value')
    ),
    prevent_initial_call=True
)

def output_cards(submit, show_override, armor_override, scale_display, weapon, bullet, target, hitzone, faction, dist, barrel, game_difficulty, silencer):
    if None in [weapon, bullet, target, hitzone, faction, dist, barrel, game_difficulty, silencer]: # no update if fields are empty, or override over 1
        raise PreventUpdate
    if show_override == True:
        if armor_override == None:
            raise PreventUpdate
        elif (armor_override > 1) or (armor_override < 0): #if armor override is on but value too large
            raise PreventUpdate
    if scale_display == True: #if we should mult. numbers by 100 for display
        display_scale = 100
    else:
        display_scale = 1
    wpn_desc = ['Weapon base damage: {}'.format(round(weapons_df.loc[weapon]['hit_power'] * display_scale, 2)), html.Br()]
    ammo = get_ammo_stats(bullet)
    npc_dict = {}
    barrel_mult = barrel_cond(barrel/100)
    if barrel >= 70: #barrel cond
        wpn_desc.append('Your barrel is dealing full damage.')
    elif barrel < 70:
        wpn_desc.append("Low barrel condition is causing you to deal {:.0%} damage.".format(barrel_mult))
    if silencer == True:
        wpn_desc.extend([html.Br(), 'Your silencer is adding 7% damage on stalker hits. '])
        if is_wpn_silenced(weapon) == True: #add new line about integral silencing
            wpn_desc.extend('This weapon is integrally silenced.')
    

    ammo_desc = ['Ammo damage multiplier: x' + str(ammo['k_hit']), 
                 html.Br(),
                 'Ammo AP value: ' + str(ammo['k_ap']*10 * display_scale)]
    if target.find('stalker_') != -1: #if is stalker
        ammo_desc.extend([html.Br(),'GBO per-ammo damage multiplier: x{}'.format(ammo['ammo_mult_stalker'])])
    elif target.find('m_gigant') != -1: #if is pseudogiant
        ammo_desc.extend([html.Br(),'GBO per-ammo damage multiplier: x{}'.format(ammo['gigant_ammo_mult'])])
    elif target.find('m_') != -1: #if is some other mutant
        ammo_desc.extend([html.Br(),'GBO per-ammo damage multiplier: x{}'.format(ammo['ammo_mult_mutant'])])
    if ammo['pellets'] > 1: #more than one pellet i.e. is buckshot
        ammo_desc.extend([html.Br(),'Buckshot-type round, has {} pellets per shot. This calculation assumes all pellets hit.'.format(ammo['pellets'])])
    
    target_desc = []
    if target.find('stalker_') != -1: #if target is stalker
        npc_dict = get_npc_stats(target)
        faction_res = npc_faction_res(faction)
        target_desc.append("The target's hitzone damage multiplier is {:.0%}. ".format(stalker_bone_mult[hitzone]))
        if show_override == True: #if there's an override, display it instead of hitzone value
            target_desc.append("Armor override applied, armor value is {}.".format(armor_override * display_scale))
        else:
            target_desc.append("Hitzone base armor value is {}.".format(get_armor(target, hitzone) * display_scale))
        target_desc.extend([
            html.Br(),
            "The target's AP resistance is {:.0%}, and non-penetrating shots have a damage cap of {:.0%}. ".format(npc_dict['ap_scale'], npc_dict['hit_fraction'])
            ])
        if faction in ['greh', 'isg', 'monolith', 'bandit']:
            target_desc.append('The target\'s faction means they take {:.0%} damage and {:.0%} AP.'.format(faction_res['dmg_res'], faction_res['ap_res']))
    elif target.find('m_') != -1: #if target is a mutant
        npc_dict = get_mutant_stats(target)
        target_desc.append('The mutant\'s hitzone damage multiplier is {:.1%}, '.format(npc_dict[hitzone]))
        if show_override == True: #if armor override is on
            target_desc.append('armor override value of {}.'.format(armor_override * display_scale))
        else:
            target_desc.append('with a base armor value of {}.'.format(get_armor(target, hitzone) * display_scale))
        target_desc.extend(
            [
                html.Br(),
                'Non-penetrating shots have a damage cap of {:.0%}, and mutants never have additional AP resistance.'.format(npc_dict['hit_fraction'])
            ])
        if npc_dict['crit_zone'] != 'none':
            target_desc.extend([html.Br(), 'This mutant takes {:.0%} extra critical damage if you shoot it in the head.'.format(npc_dict['crit_hit'])])
        if npc_dict['zombie_modifier'] < 1:
            target_desc.extend([html.Br(), 'This mutant has a hardcoded 10% damage reduction, since it is considered a zombie.'])

    game_desc = ['Your game difficulty has a {:.0%} damage multiplier.'.format(difficulty_mult[game_difficulty])]

    #create output dictionary    
    output_dict = dict(
        weapon_t = get_name(weapon),
        weapon_d = wpn_desc,
        ammo_t = get_name(bullet),
        ammo_d = ammo_desc,
        target_t = get_name(target),
        target_d = target_desc,
        game_d = game_desc
    )
    return output_dict

# Calculate damage stats

@callback(
    Output('output-div', 'children'),
    inputs=dict( # ('weapon', 'bullet', 'target', 'hitzone', 'faction', 'dist', 'barrel', 'game_difficulty', 'silencer')
        submit = Input('submit-button', 'n_clicks'),
        show_override = State('show-advanced-options', 'value'),
        armor_override = State('armor-override', 'value'),
        scale_display = State('scale-output-numbers', 'value'),
        weapon = State('weapons-dropdown', 'value'),
        bullet = State('ammo-dropdown', 'value'),
        target = State('target-type-inputs', 'value'),
        hitzone = State('hitzone-select', 'value'),
        faction = State('faction-select','value'),
        dist = State('distance-input', 'value'),
        barrel = State('barrel-condition-slider', 'value'),
        game_difficulty = State('game-difficulty-radio', 'value'),
        silencer = State('silencer', 'value')
        ),
    prevent_initial_call=True
)

def update_output(submit, show_override, armor_override, scale_display, weapon, bullet, target, hitzone, faction, dist, barrel, game_difficulty, silencer):
    if None in [weapon, bullet, target, hitzone, faction, dist, barrel, game_difficulty, silencer]:
        raise PreventUpdate
    if show_override == True:
        if armor_override == None:
            raise PreventUpdate
        elif (armor_override > 1) or (armor_override < 0): #if armor override is on but value too large
            raise PreventUpdate
    is_mutant = False
    outcome=[]
    output = []
    if scale_display == True: #if the display SHOULD be scaled
        display_scale = 100
    else:
        display_scale = 1
    #construct array for input
    input_array = [weapon, bullet, target, hitzone, faction, dist, barrel/100, game_difficulty, silencer]
    if target.find('stalker') == -1: #if not a stalker i.e. a mutant
        input_array[4] = 'other' #set faction to "other"
        is_mutant = True
    elif target.find('stalker') != -1: #if target IS stalker
        is_mutant = False
    else: #nothing in target
        raise PreventUpdate
    if show_override == False: #if user has NOT chosen to enable armor override
        armor_override = None
    
    ttk = time_to_kill(input_array)
    if is_mutant == True: #if chosen target is mutant:
        outcome = anomaly_engine_pen(mutant_hit(input_array), bullet, target, hitzone, armor_override)
        output = [
            'Estimated damage: {}, shots to kill: {}'.format(round(outcome[1] * display_scale, 4), ttk[0])
        ]
        if outcome[0] == True:
            output.extend([html.Br(), 'Shot penetrated armor!'])
    elif is_mutant == False:
        outcome = stalker_hit(input_array, armor_override)
        #print(outcome) #debugging
        if outcome [0] == True: #shot penetrates armor
            output = [
            'Estimated damage: {}, shots to kill: {}'.format(round(outcome[2] * display_scale, 6), ttk[0]),
            html.Br(),
            'Shot penetrated armor!'
            ]
        elif outcome[0] == False: #shot did not penetrate armor
            if len(outcome) > 3: #if we get to the random damage part
                output.extend([
                'Estimated average damage: {}, minimum possible damage: {}, maximum possible damage: {}.'.format(
                    round(outcome[2] * display_scale, 4),
                    round(outcome[3] * display_scale, 4),
                    round(outcome[4] * display_scale, 4)
                ),
                html.Br(), 'Average shots to kill: {}, min. shots: {}, max. shots: {}'.format(
                    ttk[0], 
                    ttk[1],
                    ttk[2]),
                html.Br(), 'First shot did not penetrate armor. New armor value: {}'.format(round(outcome[1] * display_scale, 2)),
                html.Br(), 'It would take {} shots to break armor.'.format(shots_to_pen(input_array))
            ])
            else: #no rand damage
                output.extend([
                    'Estimated damage: {}, shots to kill: {}'.format(round(outcome[2] * display_scale, 6), ttk[0]),
                    html.Br(), 'First shot did not penetrate armor. New armor value: {}'.format(round(outcome[1], 2) * display_scale),
                    html.Br(), 'It would take {} shots to break armor.'.format(shots_to_pen(input_array))
                ])
    return output

# Run the app

if __name__ == '__main__':
    app.run(debug=True)