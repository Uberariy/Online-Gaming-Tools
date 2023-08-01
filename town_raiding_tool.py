import requests
import json
import yaml
import time
import os
import sys

from pathlib import Path
from datetime import datetime, timedelta
from numpy.random import normal
from collections import defaultdict

def sleep_custom(sleep_time):
    while(1):
        sleep_randomity = normal(0.0, 0.1)
        if abs(sleep_randomity) < 0.2:
            break
    time.sleep(float(sleep_time) + sleep_randomity)

if __name__ == "__main__":
    print("Welcome to TRT - (Town Raiding Tool) by Uberietzsche. This tool finds towns, that gonna turn into ruins soon.\n"
          "It also gives you additional information about towns: \n\n"
          "  1. Town & leader names, coordinates on a map; \n"
          "  2. Mayor and town wealth (in gold); \n"
          "  3. Mayor registration date, town creation date; \n"
          "  4. Town size in chunks; \n"
          "  5. Whether a town is OPEN or not. \n"
          "\nThe code takes 20-40 minutes to run, please be patient..\n")
    print("\n ===[ STEP (0/2). PLEASE CHANGE SETTINGS IN settings.yml FILE, THEN PRESS ANY KEY TO CONTINUE. ]=== \n")
    input("")
    with open('settings.yml', 'r') as f:
        s = yaml.safe_load(f)

    save_path = Path(s['additional']['save_path'])
    saved_towns_path = save_path / Path(s['additional']['towns_file_name'])
    last_falling_towns_path = save_path / Path(s['additional']['ruining_towns_file_name'])
    time_of_new_day = timedelta(hours=s['main']['when_the_new_day_is_in_your_time_zone'])
    minimal_town_size = s['main']['minimal_town_size']
    time_to_ruin = s['additional']['time_to_ruin']
    day_amount = s['main']['day_amount']
    sleep_time = s['technical']['sleep_time']
    number_of_get_retries = s['technical']['number_of_get_retries']
    server_api_towns = s['technical']['server_api_towns']
    server_api_residents = s['technical']['server_api_residents']
    optimize_towns_parsing_if_possible = s['additional']['optimize_towns_parsing_if_possible']
    optimize_towns_parsing_if_possible_days = s['additional']['optimize_towns_parsing_if_possible_days']

    if not os.path.exists(save_path): # Create data dir, if doesn't exist
        os.makedirs(save_path)

    print("\n ===[ STEP (1/2). PARSING TOWNS DATA. PLEASE, WAIT. ]=== \n")
    '''GET towns with custom data.'''
    '''This should be done for each "time_to_ruin" days.'''
    towns_header = requests.get(server_api_towns)

    try:
        townlist = towns_header.json()["allTowns"]
        print("Getting raw list of all towns...`")
    except Exception as E:
        raise(Exception("Towns with custom data are not parsed (1)"))
    if towns_header.content == b'[]':
        raise(Exception("Towns with custom data are not parsed (2)"))

    get_tries = 0
    get_number = 0
    towns = []

    found_fresh = False
    if (optimize_towns_parsing_if_possible):
        last_date = datetime(month=1, day=1, year=2000)
        last_file = ""
        for f in os.listdir(save_path):
            if f.startswith(s['additional']['towns_file_name']):
                try:
                    fl = f[len(s['additional']['towns_file_name']):].split("_")[1:]
                    dt_towns_parsed = datetime(month=time.strptime(fl[1],'%b').tm_mon, day=int(fl[2]), year=int(fl[-1]))
                    if dt_towns_parsed > last_date:
                        last_date = dt_towns_parsed
                        last_file = f
                except Exception as E:
                    print(repr(E))
                    continue

        print(f"\nATTENTION: Found (last created) file in directory {save_path}: {last_file}!\n"
              f"It was created (according to name) {(datetime.now() - last_date).days} days ago.")
        
        if ((datetime.now() - last_date).days < optimize_towns_parsing_if_possible_days):
            print(f"According to setting 'optimize_towns_parsing_if_possible', we will use this file, because it has fresh enough town data. ")
            found_fresh = True
            with open(save_path / last_file, 'r') as f:
                towns = json.load(f)
        else:
            print(f"According to setting 'optimize_towns_parsing_if_possible', we don't use this file, because it is already too old. ")

        print(f"RULE: We skip this part ONLY if this file is younger than {optimize_towns_parsing_if_possible_days} days!")


    if (not optimize_towns_parsing_if_possible or not found_fresh):
        for townname in townlist:
            get_tries += 1

            while(1):
                '''Wait...'''
                sleep_custom(sleep_time)
                try:
                    town_resp = requests.get(f'{server_api_towns}/{townname}')
                    if town_resp.content == b'Invalid API route :(':
                        print(f"{townname} no longer exists.")
                        break
                    town_data = town_resp.json()
                    towns.append(town_data)
                    get_number += 1
                    break

                except Exception as E:
                    print(E, "=> town is not parsed (retrying)")
            
            if (get_tries % 100) == 0:
                print(f"Progress (step 1): [{get_tries} / {len(townlist)}]")
        
        with open(save_path / ('TOWNS_' + '_'.join('_'.join(time.asctime().split()).split(':'))), 'w') as f:
            json.dump(towns, f, indent = 6)
    
    min_size_for_sort = 25
    opt_size_for_sort = 75

    def sort_key(town):
        if town['stats']['numTownBlocks'] < min_size_for_sort:
            return 940 + min_size_for_sort - town['stats']['numTownBlocks']
        else:
            return abs(opt_size_for_sort - town['stats']['numTownBlocks'])

    towns.sort(key = sort_key)

    '''Parse residents one by one'''
    print("\n ===[ STEP (2/2). PARSING TOWN MAYORS & RESIDENTS TO DEFINE WHICH TOWNS GONNA FALL. PLEASE, WAIT. ]=== \n")
    ruined_towns = []
    falling_towns = defaultdict(list)

    get_tries = 0
    get_number = 0
    towns_falling_number = 0
    towns_stand_number = 0
    towns_not_interesting_number = 0
    already_ruined_number = 0

    while(1):
        '''Wait...'''
        sleep_custom(sleep_time)
        try:
            town_resp = requests.get(f'{server_api_towns}/Nokron')
            if town_resp.content == b'Invalid API route :(':
                print(f"The eternal city of Nokron no longer exists! \nDue to this catastrophy, this code is not gonna work. :( \nMaybe Uberietzsche can help with this incident.")
                sys.exit()
            town_data = town_resp.json()
            if town_data['strings']['board'] != "Space echoes like an immense tomb, yet the stars still burn. Why does the sun take so long to die?":
                print(f"The space doesn't echo like an immense tomb and the stars don't burn anymore. \nDue to this catastrophy, this code is not gonna work. :( \nMaybe Uberietzsche can help with this incident.")
                sys.exit()
            print("Uberietzsche and Nokron city are okay...")
            break

        except Exception as E:
            print(E, "=> town is not parsed (retrying)")
        
    for town in towns:
        get_tries += 1
        get_retries = 0
        if (town["perms"]["flagPerms"]['pvp'] == True) and (str(town['strings']['mayor']).startswith('NPC')):
            '''Town is probably already ruined'''
            get_number += 1
            already_ruined_number += 1
            ruined_towns.append(town)
            continue
        if (town['stats']['numTownBlocks'] < minimal_town_size):
            '''To small to list'''
            get_number += 1
            towns_not_interesting_number += 1
            continue

        '''Get mayor'''
        while(1):
            '''Wait...'''
            sleep_custom(sleep_time)
            try:
                mayor_name = town['strings']['mayor']
                mayor_resp = requests.get(f'{server_api_residents}/{mayor_name}')
                if mayor_resp.content == b'Invalid API route :(':
                    print(f"{town['strings']['mayor']} is no longer a mayor of {town['strings']['town']}")
                    break
                mayor = mayor_resp.json()
                dt_object = datetime.fromtimestamp(mayor['timestamps']['lastOnline'] // 1000)
                dt_object += timedelta(days=time_to_ruin)
                town['mayorMoney'] = mayor['stats']['balance']
                town['mayorLastOnline'] = mayor['timestamps']['lastOnline']
                town['mayorRegistred'] = mayor['timestamps']['registered']
                if dt_object >= dt_object.replace(hour=0, minute=0, second=0, microsecond=0) + time_of_new_day:
                    maximal_dt_town_falls = dt_object.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                else:
                    maximal_dt_town_falls = dt_object.replace(hour=0, minute=0, second=0, microsecond=0)
                if (maximal_dt_town_falls > (datetime.now() + timedelta(days=day_amount))):
                    '''The town falls not soon'''
                    get_number += 1
                    towns_stand_number += 1
                    break
                if (len(town["residents"]) == 1):
                    '''The town falls soon, and it has 1 citizen'''
                    get_number += 1
                    falling_towns[int(round(maximal_dt_town_falls.timestamp()))].append(town)
                    towns_falling_number += 1
                    break
                if (len(town["residents"]) != 1):
                    for resident_name in town['residents']:
                        if resident_name == town['strings']['mayor']:
                            continue
                        while(1):
                            sleep_custom(sleep_time)
                            try:
                                hier_resp = requests.get(f'{server_api_residents}/{resident_name}')
                                if hier_resp.content == b'Invalid API route :(':
                                    print(f"{resident_name} is no longer a resident of {town['strings']['town']}")
                                    break
                                hier = hier_resp.json()
                                dt_object = datetime.fromtimestamp(hier['timestamps']['lastOnline'] // 1000)
                                dt_object += timedelta(days=time_to_ruin)
                                if dt_object >= dt_object.replace(hour=0, minute=0, second=0, microsecond=0) + time_of_new_day:
                                    current_dt_town_falls = dt_object.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                                else:
                                    current_dt_town_falls = dt_object.replace(hour=0, minute=0, second=0, microsecond=0)
                                maximal_dt_town_falls = max(maximal_dt_town_falls, current_dt_town_falls)
                                break
                            except Exception as E:
                                print(E, "=> mayor is not parsed (retrying)")
                        if (maximal_dt_town_falls > (datetime.now() + timedelta(days=day_amount))):
                            '''The town falls not soon'''
                            towns_stand_number += 1
                            break
                    if (maximal_dt_town_falls <= (datetime.now() + timedelta(days=day_amount))):
                        '''The town falls soon, and but has plenty of citizens'''
                        falling_towns[int(round(maximal_dt_town_falls.timestamp()))].append(town)
                        towns_falling_number += 1
                    break
                print("Error: How do we get here?")
                break
            except Exception as E:
                print(E, "=> citizen is not parsed (retrying)")
                get_retries += 1
                if get_retries == number_of_get_retries:
                    break
        
        if (get_tries % 50) == 0:
            print(f"Progress (step 2): [{get_tries} / {len(towns)}], \tFalling soon: {towns_falling_number}, stand: {towns_stand_number}, too small: {towns_not_interesting_number}, already ruined: {already_ruined_number}")

    last_falling_towns_path = Path(str(last_falling_towns_path) + '_' + '_'.join('_'.join(time.asctime().split()).split(':')))
    print(f"\n ===[ FINISHED! THE LIST OF THE FALLING TOWNS IS BELOW AND IN FILE '{last_falling_towns_path}' ]=== \n")
    '''Main output of statistics. Each day is sorted by mayor registration date'''
    fall_tsmps = list(falling_towns.keys())
    fall_tsmps.sort()
    falling_towns = {t: falling_towns[t] for t in fall_tsmps}

    with open(last_falling_towns_path, 'w') as f:
        def printl(s, l=21):
            print(s, " " * (l - len(str(s))), end="")
            f.write(str(s) + " " * (l - len(str(s))))

        for tsmp, towns_per_day in falling_towns.items():
            if (int(tsmp) <= 3618000):
                '''Service cities...'''
                continue

            print("\nNew day of:", datetime.fromtimestamp(int(tsmp)))
            f.write("\nNew day of: " + str(datetime.fromtimestamp(int(tsmp))) + "\n")
            printl("NAME")
            printl("LEADER")
            printl("TOWN CREATION")
            printl("MAYOR REGISTRATION")
            printl("AREA", l=5)
            printl("ISOPEN ", l=7)
            printl("TOWN $", l=7)
            printl("MAYOR $", l=8)
            printl("COORDINATES-MAP")
            print("")
            f.write("\n")
            towns_per_day.sort(key = lambda t: t["timestamps"]["registered"])
            for town in towns_per_day:
                try:
                    printl(town['strings']['town'])
                    printl(town['strings']['mayor'])
                    printl(datetime.fromtimestamp(town["timestamps"]["registered"] // 1000))
                    printl(datetime.fromtimestamp(town["mayorRegistred"] // 1000))
                    printl(town['stats']['numTownBlocks'], l=5)
                    if town["status"]["isOpen"]:
                        printl("YES", l=7)
                    else:
                        printl("---", l=7)
                    printl(town['stats']["balance"], l=7)
                    printl(town["mayorMoney"], l=8)
                    printl("&x=" + str(round(town["spawn"]["x"])) + "&z=" + str(round(town["spawn"]["z"])))
                    print("")
                    f.write("\n")
                except Exception as E:
                    pass

    print("\n ===[ THIS WINDOW CAN BE CLOSED NOW, IF YOU ARE READY. ]===")
    while(1):
        input("")
