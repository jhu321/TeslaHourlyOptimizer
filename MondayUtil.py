from curses import keyname

from numpy import NaN
from moncli import client
import pandas as pd
import moncli
import DataUtils
import datetime
import math
import time

def initMonCli():
    config=DataUtils.readConfig()
    moncli.api.api_key=config['Credentials']['Monday_API']
    moncli.api.connection_timeout = 300
    return config

def NotificationLogToMonday(config, rate,battery,mode):
    board_id = config['Credentials']['Monday_NotificationLog_ID']
    try:
        board = client.get_board(id=board_id)
    except:
        print('monday could not get board')
 
    columns = board.get_columns('id','title')
    column_values= { 'text':str(rate), 'text_1':str(battery), 'text_2':str(mode)}
    item = board.add_item(item_name=datetime.datetime.now(), column_values=column_values)


def initRunLog(timestamp, currentHour, currentMin, energy_left, time_to_charge, solar_power, battery_power, grid_power, load_power, lastAlert, min_index, min_value, currentHourPrice, current5min, currentState, battReserve, operation,TodayRemainingEnergyNeed):
    runLog = {
    'timestamp':timestamp, 
    'currentHour':currentHour, 
    'currentMin':currentMin, 
    'energy_left':energy_left, 
    'time_to_charge':time_to_charge,
    'solar_power':solar_power, 
    'battery_power':battery_power, 
    'grid_power':grid_power, 
    'load_power':load_power, 
    'lastAlert':lastAlert, 
    'min_index':min_index, 
    'min_value':min_value, 
    'currentHourPrice':currentHourPrice, 
    'current5min':current5min, 
    'currentState':currentState, 
    'battReserve':battReserve, 
    'operation':operation,
    'TodayRemainingEnergyNeed':TodayRemainingEnergyNeed
    }
    return runLog

def runLogToMonday(config, runLog):
    board_id = config['Credentials']['Monday_RunLog_ID']
    try:
        board = client.get_board(id=board_id)
    except:
        print('monday could not get board')
 
    columns = board.get_columns('id','title')
    groups = board.get_groups('id','title')
    #nuke existing
    for i in groups:
        if i.title =='Current':
            group = i
    #        i.delete()
    column_name_to_id_hash = { }
    for i in columns:
        column_name_to_id_hash[i.title]=i.id

    column_values = {}
    for i in column_name_to_id_hash:
        if i in runLog:
            column_values[column_name_to_id_hash[i]]=runLog[i]
    print (column_values)
    item = group.add_item(item_name=datetime.datetime.fromtimestamp(runLog['timestamp']), column_values=column_values)



def fullSyncToMonday(config, history):
    #history=DataUtils.getHistory(config)
    board_id = config['Credentials']['Monday_Board_ID']
    try:
        board = client.get_board(id=board_id)
    except:
        print('monday could not get board')
    columns = board.get_columns('id','title')
    groups = board.get_groups('id','title')
    #nuke existing
    for i in groups:
        if i.title !='Group Title':
            i.delete()
    history_column_map= {'Hour':'hour', 'total_energy':'energy','solar':'solar','grid':'grid','battery':'battery','temp':'temp','forecast_temp':'forecasted temp','forecasted_energy':'forecasted energy','actual_price':'actual price','forecasted_price':'forecasted price','battery_price':'battery price','Battery SOC':'battery soc','Tax and Fees':'Tax and Fees','Comed Fixed':'Comed Fixed'}
    column_name_to_id_hash = { }
    date = '2022-05-30'
    for i in columns:
        column_name_to_id_hash[i.title]=i.id

    column_values = {}

    group = None

    for day in history:
        current_month=datetime.datetime.fromisoformat(day).strftime('%Y-%m')
        
        if group is None or current_month!=group.title:
            groups = board.get_groups('id','title')
            group = None
            for i in groups:
                if i.title == current_month:
                    group = i
            if group == None:
                group = board.add_group(current_month, 'id')

        for hour in history[day]['data']:
            if (history[day]['data'][hour]['hour']!=-1):
                for i in history_column_map:
                    #print(i,history_column_map[i])
                    if history_column_map[i] in history[day]['data'][hour]:
                        if not pd.isna(history[day]['data'][hour][history_column_map[i]]) and history[day]['data'][hour][history_column_map[i]] is not None and history[day]['data'][hour][history_column_map[i]] != 'NaN': 
                            column_values[column_name_to_id_hash[i]] = history[day]['data'][hour][history_column_map[i]]
                print (column_values)
                date = datetime.datetime.fromisoformat(history[day]['date'])
                date = date.replace(hour=history[day]['data'][hour]['hour'])
                print(date)
                item = group.add_item(item_name=date, column_values=column_values)
                date_value = item.column_values['date4']
                date_value.value = date
                item = item.change_column_value(column_value=date_value)

def UpdateSyncToMonday(config, history_day):
    #history=DataUtils.getHistory(config)
    board_id = config['Credentials']['Monday_Board_ID']
    board = client.get_board(id=board_id)
    columns = board.get_columns('id','title')
    groups = board.get_groups('id','title')
    
    working_day = datetime.datetime.fromisoformat(history_day['date'])
    month=working_day.strftime('%Y-%m')
    #look for the month group
    group = None
    for i in groups:
        if i.title == month:
            group=i
    if group is None:
         group = board.add_group(month, 'id')
    
    history_column_map= {'Hour':'hour', 'total_energy':'energy','solar':'solar','grid':'grid','battery':'battery','temp':'temp','forecast_temp':'forecasted temp','forecasted_energy':'forecasted energy','actual_price':'actual price','forecasted_price':'forecasted price','battery_price':'battery price','Battery SOC':'battery soc','Tax and Fees':'Tax and Fees','Comed Fixed':'Comed Fixed'}
    column_name_to_id_hash = { }
    
    for i in columns:
        column_name_to_id_hash[i.title]=i.id
    column_values = {}

#delete the day
    items=board.get_items()
    names = {}
    for i in items:
        DataUtils.add_value(names,i.name[0:10],i)

    #delete the day
    if working_day.strftime('%Y-%m-%d') in names:
        if (type(names[working_day.strftime('%Y-%m-%d')])==moncli.entities.item.Item):
            names[working_day.strftime('%Y-%m-%d')]=[names[working_day.strftime('%Y-%m-%d')]]
        print(type(names[working_day.strftime('%Y-%m-%d')]))
        for i in names[working_day.strftime('%Y-%m-%d')]:
            i.delete()


    for hour in history_day['data']:
        for i in history_column_map:
            #print(i,history_column_map[i])
            if history_column_map[i] in history_day['data'][hour]:
                if not pd.isna(history_day['data'][hour][history_column_map[i]]) and history_day['data'][hour][history_column_map[i]] is not None and history_day['data'][hour][history_column_map[i]] != 'NaN': 
                    column_values[column_name_to_id_hash[i]] = history_day['data'][hour][history_column_map[i]]
        print (column_values)
        if history_day['data'][hour]['hour']<24 and history_day['data'][hour]['hour']>=0:
            date = datetime.datetime.fromisoformat(history_day['date'])
            date = date.replace(hour=history_day['data'][hour]['hour'])
            print(date)
            item = group.add_item(item_name=date, column_values=column_values)
            date_value = item.column_values['date4']
            date_value.value = date
            item = item.change_column_value(column_value=date_value)


def addSavingsChartEntry(group,type,amount,date,column_name_to_id_hash):
    add_entry_column_values = {}
    add_entry_column_values[column_name_to_id_hash['Record Type']]=type
    add_entry_column_values[column_name_to_id_hash['Amount']]=amount
    item =group.add_item(item_name=date+' '+type, column_values=add_entry_column_values)
    date_value = item.column_values[column_name_to_id_hash['Date']]
    date_value.value = datetime.datetime.fromisoformat(date)
    item = item.change_column_value(column_value=date_value)


def UpdateSavingsChartingBaord(config,date):
    board_id = config['Credentials']['Monday_Board_ID']
    target_board_id = config['Credentials']['Savings_Charting_ID']
    board = None
    try:
        board = client.get_board(id=board_id)
        target_board = client.get_board(id=target_board_id)
    except:
        print("couldn't get boards")
    
    working_day = datetime.datetime.fromisoformat(date)
    month=working_day.strftime('%Y-%m')
    #look for the month group

    groups = target_board.get_groups('id','title')
    group = None
    for i in groups:
        if i.title == month:
            group=i
    if group is None:
         group = target_board.add_group(month, 'id')
    
    #delete the day
    items=target_board.get_items()
    names = {}
    for i in items:
        DataUtils.add_value(names,i.name[0:10],i)

    #delete the day
    if working_day.strftime('%Y-%m-%d') in names:
        if (type(names[working_day.strftime('%Y-%m-%d')])==moncli.entities.item.Item):
            names[working_day.strftime('%Y-%m-%d')]=[names[working_day.strftime('%Y-%m-%d')]]
        print(type(names[working_day.strftime('%Y-%m-%d')]))
        for i in names[working_day.strftime('%Y-%m-%d')]:
            i.delete()


    columns = target_board.get_columns('id','title')
    column_name_to_id_hash = {}
    for i in columns:
        column_name_to_id_hash[i.title]=i.id
    #print(column_name_to_id_hash)
    
    #get the items from source board
    items=board.get_items()
    names = {}
    for i in items:
        DataUtils.add_value(names,i.name[0:10],i.id)
    
    #start and end on same day
    start_date_dt = datetime.datetime.fromisoformat(date)
    end_date_dt = datetime.datetime.fromisoformat(date)
    delta = datetime.timedelta(days=1)
    

    while start_date_dt<=end_date_dt:
        if start_date_dt.strftime('%Y-%m-%d') in names.keys():
            print(names[start_date_dt.strftime('%Y-%m-%d')])
            #get the items and columns
            items = client.get_items(ids=names[start_date_dt.strftime('%Y-%m-%d')], get_column_values=True)
            #print(items)

            current_month=start_date_dt.strftime('%Y-%m')

            if group is None or current_month!=group.title:
                groups = target_board.get_groups('id','title')
                group = None
                for i in groups:
                    if i.title == current_month:
                        group = i
                if group == None:
                    group = target_board.add_group(current_month, 'id')

            energy_cost=0
            solar_savings=0
            battery_savings=0
            tou_savings=0
            full_cost=0
            flat_no_solar=0
            flat_solar=0
            

            for item in items:
                if item.column_values['actual_price'].value is None or item.column_values['grid'].value is None or item.column_values['total_energy'].value is None or item.column_values['battery'].value is None or item.column_values['battery_price'].value is None or item.column_values['Tax and Fees'].value is None or item.column_values['Comed Fixed'].value is None:
                    continue
                energy_cost += (item.column_values['grid'].value/1000) * (item.column_values['actual_price'].value/100 + item.column_values['Tax and Fees'].value)
                flat_no_solar += (item.column_values['total_energy'].value/1000) * (item.column_values['Comed Fixed'].value + item.column_values['Tax and Fees'].value)
                flat_solar += (item.column_values['grid'].value/1000) * (item.column_values['Comed Fixed'].value + item.column_values['Tax and Fees'].value)
                battery_savings += (((item.column_values['grid'].value+item.column_values['battery'].value)/1000) * (item.column_values['actual_price'].value/100)) - (((item.column_values['grid'].value/1000) * (item.column_values['actual_price'].value/100)) + ((item.column_values['battery'].value/1000) * (item.column_values['battery_price'].value/100)))
            print(energy_cost,flat_solar,flat_no_solar,battery_savings)
            addSavingsChartEntry(group, "Solar Savings",flat_no_solar-flat_solar,start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
            addSavingsChartEntry(group, "Actual Energy Cost",energy_cost,start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
            addSavingsChartEntry(group, "Battery Savings",battery_savings,start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
            addSavingsChartEntry(group, "TOU Savings",flat_no_solar-((flat_no_solar-flat_solar)+battery_savings+energy_cost),start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
        start_date_dt+=delta



def PopSavingsChartingBaord(config):
    board_id = config['Credentials']['Monday_Board_ID']
    target_board_id = config['Credentials']['Savings_Charting_ID']
    board = None
    try:
        board = client.get_board(id=board_id)
        target_board = client.get_board(id=target_board_id)
    except:
        print("couldn't get boards")
    
    groups = target_board.get_groups('id','title')
    #nuke existing
    for i in groups:
        if i.title !='Group Title':
            i.delete()
    group = None
    columns = target_board.get_columns('id','title')
    column_name_to_id_hash = {}
    for i in columns:
        column_name_to_id_hash[i.title]=i.id
    print(column_name_to_id_hash)
    items=board.get_items()
    names = {}
    for i in items:
        DataUtils.add_value(names,i.name[0:10],i.id)
#        names[]
#       names[i.name]=i.id

    
    print (min(names.keys()))
    start_date = min(names.keys())[0:10]
    print(start_date)
    end_date = max(names.keys())[0:10]
    print(end_date)

    start_date_dt = datetime.datetime.fromisoformat(start_date)
    end_date_dt = datetime.datetime.fromisoformat(end_date)
    delta = datetime.timedelta(days=1)
    

    while start_date_dt<=end_date_dt:
        print(names[start_date_dt.strftime('%Y-%m-%d')])
        #get the items and columns
        items = client.get_items(ids=names[start_date_dt.strftime('%Y-%m-%d')], get_column_values=True)
        #print(items)

        current_month=start_date_dt.strftime('%Y-%m')

        if group is None or current_month!=group.title:
            groups = target_board.get_groups('id','title')
            group = None
            for i in groups:
                if i.title == current_month:
                    group = i
            if group == None:
                group = target_board.add_group(current_month, 'id')

        energy_cost=0
        solar_savings=0
        battery_savings=0
        tou_savings=0
        full_cost=0
        flat_no_solar=0
        flat_solar=0
        for item in items:
            if item.column_values['actual_price'].value is None or item.column_values['grid'].value is None or item.column_values['total_energy'].value is None or item.column_values['battery'].value is None or item.column_values['battery_price'].value is None:
                continue
            energy_cost += (item.column_values['grid'].value/1000) * (item.column_values['actual_price'].value/100 + item.column_values['Tax and Fees'].value)
            flat_no_solar += (item.column_values['total_energy'].value/1000) * (item.column_values['Comed Fixed'].value + item.column_values['Tax and Fees'].value)
            flat_solar += (item.column_values['grid'].value/1000) * (item.column_values['Comed Fixed'].value + item.column_values['Tax and Fees'].value)
            battery_savings += (((item.column_values['grid'].value+item.column_values['battery'].value)/1000) * (item.column_values['actual_price'].value/100)) - (((item.column_values['grid'].value/1000) * (item.column_values['actual_price'].value/100)) + ((item.column_values['battery'].value/1000) * (item.column_values['battery_price'].value/100)))
        print(energy_cost,flat_solar,flat_no_solar,battery_savings)
        addSavingsChartEntry(group, "Solar Savings",flat_no_solar-flat_solar,start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
        addSavingsChartEntry(group, "Actual Energy Cost",energy_cost,start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
        addSavingsChartEntry(group, "Battery Savings",battery_savings,start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
        addSavingsChartEntry(group, "TOU Savings",flat_no_solar-((flat_no_solar-flat_solar)+battery_savings+energy_cost),start_date_dt.strftime('%Y-%m-%d'),column_name_to_id_hash)
        start_date_dt+=delta



if __name__ == "__main__":
    config=initMonCli()
    history = DataUtils.getHistory(config)
    for i in history:
            history_day=datetime.datetime.strptime(i,'%Y-%m-%d')
            today=datetime.datetime.today()
            today+=datetime.timedelta(days=-16)
            if (history_day>today):
                UpdateSyncToMonday(config,history[history_day.strftime('%Y-%m-%d')])
                UpdateSavingsChartingBaord(config,history_day.strftime('%Y-%m-%d'))
                print(history_day)
    #PopSavingsChartingBaord(config)
   
    #UpdateSyncToMonday(config,history['2022-06-05'])
    #UpdateSavingsChartingBaord(config,'2022-06-05')

    #DataUtils.popDataWithPricing(config,history['2022-06-14'],True)
    #DataUtils.popDataWithPricing(config,history['2022-06-15'],True)
    #DataUtils.popDataWithPricing(config,history['2022-06-16'],True)
    #DataUtils.saveHistory(history)
    #UpdateSavingsChartingBaord(config,'2022-07-05')
    #runLog=initRunLog(math.trunc(datetime.datetime.now().timestamp()),10,13,123,431,123,432,123,432,123,432,123,431,123,523,123,'asdkjs')
    #runLogToMonday(config, runLog)
    #NotificationLogToMonday(config,'asdf','gfds','asdfasdf')