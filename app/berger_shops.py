import requests, pytz, os
import pandas as pd
from datetime import datetime
from babel.dates import format_datetime
from .utilities import push_b2_file,log_msg, get_now_french
import os, requests, time, pytz

##################################################################
# BASIC SET-UP
##################################################################
# BASIC SET-UP
GOOGLEMAPS_KEY = os.getenv('GOOGLEMAPS_KEY')
HTML_PARIS_SHOPS_LOCAL = os.path.abspath('berger_shops.html')
HTML_PARIS_SHOPS_BB = 'berger_shops.html'
list_shops = {
    'Bacillus': {'Type':'Boulangerie',
                 'AddressDescription': "100 r. des Dames", 
                 'FullAddress': "Bacillus, 100 Rue des Dames, 75017 Paris, France",
                 'Location':"V8M8+4V Paris, France",
                 'Phone':"+33767734617",
                 'PlaceID':"ChIJQQYz4Mdv5kcRybznq5-V33M",
                 'maplink':'https://maps.app.goo.gl/NxYH3Q7DxLbUQRTw8'},
    'B. du Parc Monceau':  {'Type':'Boulangerie',
                            'AddressDescription': "51 r. de Prony", 
                            'FullAddress': "Boulangerie du Parc Monceau (51 Rue de Prony, 75017 Paris, France )",
                            'Location':"V8J3+RR Paris, France",
                            'Phone':"+33142274125",
                            'PlaceID':"ChIJSz4ofr5v5kcRgHkHz6KCzrU",
                            'maplink':'https://maps.app.goo.gl/sdJtbgM5vH3RHBWD7'},
    'Maison Marques': {'Type':'Boulangerie',
                       'AddressDescription': "6 r. de Lévis", 
                       'FullAddress': "Maison Marques (6 R. de Lévis, 75017 Paris, France)",
                       'Location':"V8J8+PG Paris, France",'Phone':"+33143874242",
                       'PlaceID':"ChIJ8Sf10bZv5kcRwtDXjCLe6cM",
                       'maplink':'https://maps.app.goo.gl/uxSohQTgXpsfpgAb9'},
    'Léonie': {'Type':'Boulangerie',
               'AddressDescription': 
                   "96 r. de Lévis",
                   'FullAddress': "Boulangerie Léonie (V8P6+2H Paris 96 R. de Lévis, 75017 Paris, France)", 
                   'Location':"V8P6+2H Paris, France",
                   'Phone':"+33142272827",
                   'PlaceID':"ChIJ0e8O8bpv5kcR8rkelMVn_pg", 
                   'maplink':'https://maps.app.goo.gl/MqiexUTSncTcY3wj7'},
    'Les Enfants Gâtés': {'Type':'Boulangerie',
                          'AddressDescription': "7 r. Cardinet",
                          'FullAddress': "Les Enfants Gâtés (7 Rue Cardinet, 75017 Paris, France)",
                          'Location':"V8J2+JM Paris, France",
                          'Phone':"+33147635570",
                          'PlaceID':"ChIJKcMPHb5v5kcRBRRZpc98Tog",
                          'maplink':'https://maps.app.goo.gl/mZNooEY3o1EEKfcc6'},
    'Meringaie': {'Type':'Boulangerie',
                  'AddressDescription': '21 r. de Lévis',
                  'FullAddress': 'La Meringaie 21 R. de Lévis',
                  'Location':'V8J8+V5 Paris, France',
                  'Phone':"+33144719416",
                  'PlaceID':'ChIJZaxP1LBv5kcRQKASCZUfnz8', 
                  'maplink': 'https://maps.app.goo.gl/upej8Q3mAXF1Jrfx6'},
    'Monoprix': {'Type':'Supermarché','AddressDescription': 
                 '13 r. de Lévis',
                 'FullAddress': 'Monoprix 13 R. de Lévis',
                 'Location':'V8J8+Q6 Paris, France',
                 'Phone':"+33143872360",
                 'PlaceID':'ChIJW8_mKrdv5kcRKyd7WTgkaZQ', 
                 'maplink':'https://maps.app.goo.gl/mXF58WEf6DAFm6zP8'},
    'Monoprix Villiers': {'Type':'Supermarché',
                          'AddressDescription': '48 av. de Villiers',
                          'FullAddress': 'Monop 48 Av. de Villiers', 
                          'Location':'V8M5+84 Paris, France', 
                          'Phone':"+33153819122",
                          'PlaceID':'ChIJsYAh87tv5kcRChrmMul1Db0', 
                          'maplink': 'https://maps.app.goo.gl/Rb3i4FKxpgtGKuKm7'},
    'Cocci Market': {'Type':'Supérette',
                     'AddressDescription':'49 r. de Prony',
                     'FullAddress':'',
                     'Location':'',
                     'Phone': '+33 1 42 27 94 97',
                     'PlaceID':'ChIJ09Odgb5v5kcRT2-fK4A8t2I',
                     'maplink':'https://maps.app.goo.gl/ftn1FX53RDdjuqny9'},
    'Carrefour Market': {'Type':'Supérette',
                         'AddressDescription':'85 r. Jouffroy',
                         'FullAddress':'',
                         'Location':'',
                         'Phone':'+33180502081',
                         'PlaceID':'ChIJgygnxb1v5kcR7KGCIyd7iBA',
                         'maplink':'https://maps.app.goo.gl/J52AiCf2xzEHcZ4aA'},
    "Terroirs d'avenir": {'Type':'Epicerie',
                          'AddressDescription':'123 r. des Dames',
                          'FullAddress':'',
                          'Location':'',
                          'Phone':'+33184798847',
                          'PlaceID':'ChIJT-Swfv5v5kcRwpDk8nVfzaw',
                          'maplink':'https://maps.app.goo.gl/dVgpPDX6vmjnLWMf7'},
    'Art potager': {'Type':'Epicerie',
                    'AddressDescription':'49 r. de Lévis',
                    'FullAddress':'',
                    'Location':'',
                    'Phone':'+33768175201',
                    'PlaceID':'ChIJw7Ig__lv5kcRSOVgpnCC8u0',
                    'maplink':'https://maps.app.goo.gl/FPyYYyoPPekKCwQL6'},
    'Umai': {'Type':'Epicerie',
             'AddressDescription': '102 r. des Dames',
             'FullAddress': '',
             'Location': '',
             'Phone':'+33983036044',
             'PlaceID':'ChIJfXHKtQ9v5kcRITXE4sE5c10',
             'maplink':'https://maps.app.goo.gl/HFQymdKyXaL7aoEY9'},
    'Lévis terrasse': {'Type':'Epicerie',
                       'AddressDescription':'33 r. de Lévis',
                       'FullAddress':'',
                       'Location':'',
                       'Phone':'+33147632138',
                       'PlaceID':'ChIJ79BpxbBv5kcRfk6iu525zjA',
                       'maplink':'https://maps.app.goo.gl/66VNotdsF5F9BNMB6'},
    'Famille Mary': {'Type':'Epicerie',
                     'AddressDescription':'44 r. de Lévis',
                     'FullAddress':'',
                     'Location':'',
                     'Phone':'+33142127270',
                     'PlaceID':'ChIJcYx2lbBv5kcRaftzwc1TAGk',
                     'maplink':'https://maps.app.goo.gl/d8tDQivQgEEgvesM9'},
    'Fromage et détail': {'Type':'Fromager',
                          'AddressDescription':'43 r. de Lévis',
                          'FullAddress':'',
                          'Location':'',
                          'Phone':'+33147636144',
                          'PlaceID':'ChIJKxrlwLBv5kcRNy966lGYAcE',
                          'maplink':'https://maps.app.goo.gl/KXJLhKE7xn76MjZ89'},
    'Repaire de Bacchus': {'Type':'Caviste',
                           'AddressDescription':'51 r. de Lévis',
                           'FullAddress':'',
                           'Location':'',
                           'Phone':'+33172636834',
                           'PlaceID':'ChIJwSAnlLBv5kcRjPsDSFPopNM',
                           'maplink':'https://maps.app.goo.gl/sY4hx3PzfoRr54Pi6'},
    'Mariage Frères': {'Type': 'Thé',
                       'AddressDescription':'260 r. du Fbg. S.Honoré',
                       'FullAddress':'',
                       'Locaton': '',
                       'Phone':'+33146221854',
                       'PlaceID':'ChIJrWGhTJVv5kcRvfgRhqT2jGA',
                       'maplink':'https://maps.app.goo.gl/5mY5eB7gj9krc6JcA'},
    'Picard Prony': {'Type': 'Surgelés',
                     'AddressDescription': '55 r. de Prony',
                     'FullAddress':'',
                     'Location':'',
                     'Phone':'+33146228210',
                     'PlaceID':'ChIJa16k171v5kcRt3YGcMu-Elo',
                     'maplink':'https://maps.app.goo.gl/xoJDW1qmyvEqGKbD8'},
    'Picard Lévis': {'Type':'Surgelés',
                     'AddressDescription':'21 r. Legendre',
                     'FullAddress':'',
                     'Location':'',
                     'Phone':'+33147630114',
                     'PlaceID':'ChIJz26RmrBv5kcRPJTx-iMTsTk',
                     'maplink':'https://maps.app.goo.gl/GG9jz4XvDVK9TZfV8'},
    'Ph. de la rotonde': {'Type':'Pharmacie',
                                'AddressDescription': ' 1 r. de Phalsbourg',
                                'FullAddress': 'xxx',
                                'Location': '',
                                'Phone': '+33 1 45 74 05 17',
                                'PlaceID': 'ChIJrWGhTJVv5kcRvfgRhqT2jGA',
                                'maplink': 'https://maps.app.goo.gl/tE7j2JcQcyPivCMX9'},
    'Ph. de la terrasse': {'Type':'Pharmacie',
                        'AddressDescription': '35 r. de Lévis',
                        'FullAddress': '',
                        'Location':'',
                        'Phone': '+33 1 42 27 49 51',
                        'PlaceID':'ChIJaX0VxbBv5kcRQhIeustkWD4',
                        'maplink':'https://maps.app.goo.gl/5AhYnZUX6aAauSoB7'},
    'Pharmacie Ayoun': {'Type':'Pharmacie',
                        'AddressDescription': '8 av. de Villiers',
                        'FullAddress':'',
                        'Location':'',
                        'PlaceID':'ChIJ___DK7dv5kcRqUJRWvoKXog',
                        'Phone':'',
                        'maplink':'https://maps.app.goo.gl/mLUYNHWbfKsWTNnc9'},
    'Pharmacie Prony': {'Type':'Pharmacie',
                        'AddressDescription':'53 r. de Prony',
                        'FullAddress':'',
                        'Location':'',
                        'Phone': '+33 1 47 63 30 16',
                        'PlaceID':'ChIJAw_v1b1v5kcRFPtYAjgd4Pw',
                        'maplink':'https://maps.app.goo.gl/K8XKCk8yWHq6bvKw5'}
}



##################################################################
# GET GOOGLE MAPS OPENING HOURS FOR A BUSINESS
def get_shop_opening_hours(shop_name, place_id):
    # Query Google Maps
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "language": "fr",
        "fields": "name,opening_hours",
        "key": GOOGLEMAPS_KEY
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    # Decode the results
    try:
        info = data["result"].get("opening_hours", {})
    except Exception as e:
        log_msg(f'Error in get_shop_opening_hours for {shop_name} {str(e)}')
        info = None
    return info

##################################################################
# MAKE HTML TABLE WITH CONTACT DETAILS OF SHOPS
def make_shop_contact_table(list_shops):
    log_msg('Making HTML table of shop contact details')
    html = '\n\n<TABLE style="line-height: 1.4;font-size: 0.75em;">\n<TR><TH style="text-align: left; color: #dd6666">Type</TH><TH style="text-align: left; color: #dd6666">Nom</TH><TH style="text-align: left; color: #dd6666">Adresse</TH><TH style="text-align: center; color: #dd6666">Lien carte</TH><TH style="text-align: center; color: #dd6666">Tél.</TH>\n</TR>\n'
    previous_type = ''
    for name in list_shops:
        type_shop = list_shops[name]['Type']
        if type_shop == previous_type:
            name_type = ''
        else:
            name_type = type_shop
            previous_type = type_shop
        address = list_shops[name]['AddressDescription']
        link = list_shops[name]['maplink']
        phone = list_shops[name]['Phone']
        html += f"<TR><TD><B>{name_type}</B></TD><TD>{name}</TD><TD>{address}</TD><TD style='text-align: center'><A HREF='{link}'>Map</A></TD><TD style='text-align: center; '><A HREF='{phone}' style='text-decoration: none;' >📞</A></TD></TR>\n"
    html += '</TABLE></HTML>\n'
    return html


##################################################################
# MAKE HTML TABLE WITH OPENING TIMES
def make_shop_times_HTML():
    # Iterate through shops
    list_hours = {}
    for shop in list_shops: #list_bakeries:
        print(f'Querying opening hours for {shop}')
        info = get_shop_opening_hours(shop, list_shops[shop]['PlaceID'])
        list_hours[shop] = info
    
    # Make Pandas table with opening times
    log_msg('Making Pandas table of shop opening times')
    day_names = ['Dim.','Lun.','Mar.','Mer.','Jeu.','Ven.','Sam.']
    map_times = pd.DataFrame(index=list_shops.keys(),columns=day_names)
    map_times.loc[:,:] = ''
    for shop in list_shops:
        if list_hours[shop] is None:
            map_times.loc[shop, :] = '-'
        else:
            if not ('periods' in list_hours[shop]):
                print('no -periods- field in ', shop)
            else:
                for m in list_hours[shop]['periods']:
                    times_open = m['open']
                    times_close = m['close']
                    if True or (times_open['day'] == times_close['day']):
                        day_number = times_open['day']
                        day_name = day_names[day_number]
                        s = ''
                        for t in [times_open['time'],times_close['time']]:
                            if len(t) == 4:
                                if t[0] == '0':
                                    t_hours = t[1]
                                else:
                                    t_hours = t[:2]
                                if t[-2:] == '00':
                                    t_min = ''
                                else:
                                    t_min = t[2:]
                                s += t_hours + 'h' + t_min
                            else:
                                s += '?'
                            s += '-'
                        s = s[:-1]
                        if map_times.loc[shop, day_name] == '':
                            sep = ''
                        else:
                            sep = '<BR>'
                        map_times.loc[shop, day_name] = map_times.loc[shop, day_name] + sep + s
                    else:
                        map_times.loc[shop, :] = '.'
    map_times = map_times.reset_index().rename({'index':'Nom'}, axis=1)
    map_times[' '] = [list_shops[s]['Type'] for s in map_times.Nom]
    map_times.set_index(' ', inplace=True)
    for i in range(1, map_times.shape[0]):
        for j in range(1, map_times.shape[1]):
            if map_times.iloc[i,j] == '':
                map_times.iloc[i,j] = 'Fermé'

    # Make HTML table
    log_msg('Making HTML table of shop opening times')
    html = '\n\n<TABLE style="border-collapse: collapse; line-height: 1.4;font-size: 0.75em;">\n<TR><TH style="text-align: left; color: #dd6666"></TH><TH style="text-align: left; color: #dd6666">Nom</TH>'
    for d in day_names: 
        html += f'<TH style="text-align: left; color: #dd6666;text-align: center">{d}</TH>'
    html += '</TR>\n'
    previous_type = ''
    for i in range(map_times.shape[0]):
        row = map_times.iloc[i,:]
        type_shop = row.name
        name_shop = row['Nom']
        if type_shop == previous_type:
            name_type = ''
        else:
            name_type = type_shop
            previous_type = type_shop
        html += f'<TR style="border-bottom: 1px solid #ddd;"><TD  style="padding: 0 16px;"><B>{name_type}</BR></TD><TD>{name_shop}</TD>'
        for d in day_names:
            html += f'<TD style="text-align: center;">{row[d]}</TD>'
        html += '</TR>\n'
    html += '</TABLE></HTML>\n'
    html += f'<BR><span style="font-size: 10px;">Mise à jour: {get_now_french()}</SPAN><BR>'

    # Return table
    return html

##################################################################
# MAKE OVERALL HTML
def make_overall_shop_HTML():
    # Create HTML content
    html_times = make_shop_times_HTML()
    html_contact = make_shop_contact_table(list_shops)
    html = '<H4>Horaires</H4>' + html_times + '<BR><H4>Contact</H4>' + html_contact
        
    # Save HTML to local file
    log_msg('\make_overall_shop_HTML Saving HTML')
    with open(HTML_PARIS_SHOPS_LOCAL,'wt') as f:
        f.write(html)
    log_msg('\make_overall_shop_HTML Done')
    
    # Push the file to BB
    log_msg('make_overall_shop_HTML pushing to BB')
    push_b2_file('bergershops', HTML_PARIS_SHOPS_LOCAL, HTML_PARIS_SHOPS_BB)
    log_msg(f'make_overall_shop_HTML table pushed to BB in {HTML_PARIS_SHOPS_BB}')

    
##################################################################
# REGULAR CALL TO THE make_overall_shop_HTML()
def periodic_query_berger_shops():
    log_msg('Entering background function periodic_query_berger_shops ')
    log_msg('periodic_query_berger_shops sleep')
    time.sleep(1)
    log_msg('periodic_query_berger_shops sleep end')
    while True:
        log_msg('periodic_query_berger_shops loop step ')
        try:
            make_overall_shop_HTML()
        except Exception as e:
            log_msg('Error in periodic_query_berger_shops update: ' + str(e))
        else:
            log_msg('periodic_query_berger_shops update done')
        time.sleep(2 * 60 * 60)
