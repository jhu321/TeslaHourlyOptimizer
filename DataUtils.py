from ast import dump
from cmath import nan
from json import JSONDecoder
from time import clock_settime
from numpy import average, power
import requests
import datetime
import teslapy
import geopy.distance
import pytz
import json
import configparser
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from unicodedata import normalize
import copy
import csv

def readConfig():
   config = configparser.ConfigParser()
   config.read('config.txt')
   return config

def initHourlyHistory():
    hourly_history={}
    for k in range(24):
        hourly_history['hour'+str(k)]={'hour':-1,'energy':0,'solar':0 ,'grid':0,'battery':0, 'temp':0,'forecasted energy':0, 'forecasted temp':0, 'actual price':0,'forecasted price':0,'Tax and Fees':0.01783, 'Comed Fixed':0.11041}
    return hourly_history


def getSiteTOUHistory(config, date, hourly_history):
    try:
        teslaUserID=config['Credentials']['TeslaUserID']

        local = pytz.timezone('US/Central')
        s_date = local.localize(datetime.datetime(
        date.year,
        date.month,
        date.day,
        0,
        0,
        0,
        0
        ), is_dst=None)

        e_date = local.localize(datetime.datetime(
        date.year,
        date.month,
        date.day,
        23,
        59,
        59,
        0
        ), is_dst=None)

        print(datetime.datetime.strftime(
               s_date.astimezone(pytz.utc), 
               '%Y-%m-%dT%H:%M:%SZ'))
        print(datetime.datetime.strftime(
        e_date.astimezone(pytz.utc), 
        '%Y-%m-%dT%H:%M:%SZ'))
        print(s_date)

        with teslapy.Tesla(teslaUserID) as tesla:
            battery = tesla.battery_list()
            powerHistory= battery[0].get_calendar_history_data(kind='power', period='day', start_date=datetime.datetime.strftime(
               s_date.astimezone(pytz.utc), 
               '%Y-%m-%dT%H:%M:%SZ'),end_date=datetime.datetime.strftime(
               e_date.astimezone(pytz.utc), 
               '%Y-%m-%dT%H:%M:%SZ'))
            #print(powerHistory)
            power=0
            #reinit to 0 history for the day so repeated runs don't end up cumulative 
            for i in range(24):
                hourly_history['hour'+str(i)]['energy']=0
                hourly_history['hour'+str(i)]['solar']=0
                hourly_history['hour'+str(i)]['battery']=0
                hourly_history['hour'+str(i)]['grid']=0

            #print(hourly_history)
            for i in powerHistory['time_series']:
                d=datetime.datetime.fromisoformat(i['timestamp'])
                #if d.hour==1 and d.day==24:
                #print(d.hour)
                #init if missing
                if 'solar' not in hourly_history['hour'+str(d.hour)]:
                    hourly_history['hour'+str(d.hour)]['solar']=0
                if 'battery' not in hourly_history['hour'+str(d.hour)]:
                    hourly_history['hour'+str(d.hour)]['battery']=0
                if 'grid' not in hourly_history['hour'+str(d.hour)]:
                    hourly_history['hour'+str(d.hour)]['grid']=0
                if 'hour' not in hourly_history['hour'+str(d.hour)]:
                    hourly_history['hour'+str(d.hour)]['hour']=0
                if 'energy' not in hourly_history['hour'+str(d.hour)]:
                    hourly_history['hour'+str(d.hour)]['energy']=0

                hourly_history['hour'+str(d.hour)]['energy']+=(i['solar_power']+i['battery_power']+i['grid_power'])*(1/12)
                hourly_history['hour'+str(d.hour)]['solar']+=(i['solar_power'])*(1/12)
                hourly_history['hour'+str(d.hour)]['battery']+=(i['battery_power'])*(1/12)
                hourly_history['hour'+str(d.hour)]['grid']+=(i['grid_power'])*(1/12)
                hourly_history['hour'+str(d.hour)]['hour']=d.hour
            print(hourly_history)
            #print(i)
            return hourly_history
            
            #print(vehicles[0].get_vehicle_data()['charge_state']['charging_state'])
        #print(vehicles[0].get_vehicle_data())

    except Exception as e: 
        print(e)
        return hourly_history

def generateHistory(config,num_days):
    count = num_days
    now = datetime.datetime.today()
    totalHistory={}
    while count>0:
        d = datetime.timedelta(days = count)
        print(d)
        current_date = now - d 
        totalHistory[current_date.strftime('%Y-%m-%d')]={'date': current_date.strftime('%Y-%m-%d'), 'data' : getSiteTOUHistory(config,current_date,initHourlyHistory())}
        count=count-1  
    return totalHistory    

def createHistory(config,current_date,totalHistory):
        print("create history:"+ current_date.strftime('%Y-%m-%d') )
        if current_date.strftime('%Y-%m-%d') in totalHistory:
            history_day = totalHistory[current_date.strftime('%Y-%m-%d')]['data']
            getSiteTOUHistory(config,current_date,history_day)
        else:
            history_day = initHourlyHistory()
            totalHistory[current_date.strftime('%Y-%m-%d')]={'date': current_date.strftime('%Y-%m-%d'), 'data' : getSiteTOUHistory(config,current_date,history_day)}
        print(history_day)


def updateHistory(config,num_days,totalHistory):
    count = num_days
    now = datetime.datetime.today()
    while count>=0:
        d = datetime.timedelta(days = count)
        print(d)
        current_date = now - d 
        if current_date.strftime('%Y-%m-%d') in totalHistory:
            history_day = totalHistory[current_date.strftime('%Y-%m-%d')]['data']
            getSiteTOUHistory(config,current_date,history_day)
        else:
            history_day = initHourlyHistory()
            totalHistory[current_date.strftime('%Y-%m-%d')]={'date': current_date.strftime('%Y-%m-%d'), 'data' : getSiteTOUHistory(config,current_date,history_day)}
        count=count-1  
    return totalHistory    


def calcAvgEnergyUsageByHour(history):
    results = {}
    for k in range(24):
        working_energy=0
        for i in history:
            #print(i)
            working_energy+=history[i]['data']['hour'+str(k)]['energy']
        results['hour'+str(k)]=working_energy/len(history)
    return results

def kelvinToFahrenheit(kelvin):
    return kelvin * 1.8 - 459.67

def getWeather(config,dt):

    try:
        with open('weather_history.json','r') as weather_history_file:
            w_hist = json.load(weather_history_file)
    except FileNotFoundError:
            w_hist = {}
    try:        
        if (str(dt) not in w_hist and datetime.datetime.fromtimestamp(dt) < datetime.datetime.now()):
         #if (str(dt) not in w_hist):
            owm =config['Credentials']['OMW_key']
            print(owm)
            onecall_request = 'http://api.openweathermap.org/data/3.0/onecall/timemachine?lat=%s&lon=%s&dt=%s&appid=%s'
            owm_url = onecall_request % (config['Tesla_Cars']['home_lat'],config['Tesla_Cars']['home_long'],str(int(dt)),owm)
            print(owm_url)
            results = requests.get(owm_url)
            if results.status_code==429:
                return 
            print(results.json())
            w_hist[str(dt)]=results.json()
            with open('weather_history.json','w') as weather_history_file:
                json.dump(w_hist,weather_history_file)
    except:
        print("too many calls moving on")
    if str(dt) in w_hist:
        return w_hist[str(dt)]
    else:
        return None

#this is a force calculation from start
def calcBattsOC(history):
#since history was created chronogically insertion order is guaranteed
    working_energy= 25000
    for i in history:
        for h in history[i]['data']:
            working_energy-=history[i]['data'][h]['battery']
            if working_energy>42000:
                working_energy=42000
            history[i]['data'][h]['battery soc']=working_energy






def getPreviousCharge(date, hour, history):
    current_date= datetime.datetime.fromisoformat(date)
    yesterday=datetime.datetime.fromisoformat(date)
    yesterday+=datetime.timedelta(days=-1)
    #create a dictionary that is a union of 2 day's prices
    working_set = {}
    if yesterday.strftime('%Y-%m-%d') in history:
        for i in history[yesterday.strftime('%Y-%m-%d')]['data']:
            if 'battery price' in history[yesterday.strftime('%Y-%m-%d')]['data'][i]:
                working_set[history[yesterday.strftime('%Y-%m-%d')]['data'][i]['hour']-24]=history[yesterday.strftime('%Y-%m-%d')]['data'][i]['battery price']
            else:
                working_set[history[yesterday.strftime('%Y-%m-%d')]['data'][i]['hour']-24]=-99

    if current_date.strftime('%Y-%m-%d') in history:
        for i in history[current_date.strftime('%Y-%m-%d')]['data']:
            if 'battery price' in history[current_date.strftime('%Y-%m-%d')]['data'][i]:
                working_set[history[current_date.strftime('%Y-%m-%d')]['data'][i]['hour']]=history[current_date.strftime('%Y-%m-%d')]['data'][i]['battery price']
            else:
                working_set[history[current_date.strftime('%Y-%m-%d')]['data'][i]['hour']]=-99
    print(current_date,yesterday)
    print(working_set)

# we should have a working set now...
    for i in range(hour,min(working_set),-1):
        
        if i in working_set and working_set[i]!=-99 and not pd.isna(working_set[i]):
            return working_set[i]
    # we are still here... so we must've never charged... set the battery to free
    return 0

 
def popDataWithBattPricing(date,data, history):
    #assumption grid charging or solar charging value is whatever prevalant price is since electricity is a commodity
    #loop through and any hour where batt is negative we can assume that price
    current_date = datetime.datetime.fromisoformat(date)
    print("popDatawithBatt",current_date)
    if(current_date.date()<=datetime.datetime.now().date()):
        for i in data['data']:
            if data['data'][i]['battery'] < 0:
                current_energy_value = getPreviousCharge(date,data['data'][i]['hour']-1, history ) * (data['data'][i]['battery soc']+data['data'][i]['battery'])
                new_energy_value = data['data'][i]['actual price']*data['data'][i]['battery'] * -1
                new_price = (new_energy_value+current_energy_value) / data['data'][i]['battery soc']
                print(current_energy_value,new_energy_value,new_price)
                data['data'][i]['battery price']=new_price
            else:
                data['data'][i]['battery price']=getPreviousCharge(date,data['data'][i]['hour']-1, history )




def popDataWithPricing(config,data, forceupdate):
    #tomorrow=datetime.datetime.today()
    #tomorrow+=datetime.timedelta(days=1)
    #today=datetime.datetime.today().strftime('%Y%m%d')
    #tomorrow=tomorrow.strftime('%Y%m%d')
    date= datetime.datetime.fromisoformat(data['date'])
    
    #only populate if there no price on hour0
    if(data['data']['hour0']['actual price']!=0 and forceupdate!=True):
        return 
    
    URL='https://hourlypricing.comed.com/rrtp/ServletFeed?type=pricingtabledual&date='+date.strftime('%Y%m%d')
    page=requests.get(URL,verify=False)
    # first try tomorrow to see if we have data... if we do then use tomorrow.. else today
    if(len(page.text) <=5):
        #we're here so we must not have any data... return
        return
    tab='<table><tr><td>time</td><td>forecast</td><td>actual</td></tr>'+page.text+'</table>'
    tab=tab.replace("&cent;","")
    #print(tab)
    table_MN = pd.read_html(tab,header=0)
    print(table_MN[0])
    forecast = table_MN[0]['forecast']
    actual = table_MN[0]['actual']
 #   print(actual)
    
    #actual.pop(0)
    #forecast.pop(0)
    

   # print(actual)

    newActual=[]
    newForecast=[]
# we need to fix the data because its hour ending and not hour beginning
    for i in range(len(actual)):
        print(i,i+1)
        if i+1<len(actual):
            newActual.append(actual[i+1])
            newForecast.append(forecast[i+1])

#default to same as hour ending 11pm
    newActual.append(actual[23].copy())
    newForecast.append(forecast[23].copy())
 
#    asdfasdfasdf

# now we need to fix hour ending midnight
    d = datetime.timedelta(days = 1)
    tomorrow = date +d
    URL='https://hourlypricing.comed.com/rrtp/ServletFeed?type=pricingtabledual&date='+date.strftime('%Y%m%d')
    page=requests.get(URL,verify=False)
    # first try tomorrow to see if we have data... if we do then use tomorrow.. else today
    if(len(page.text) >5):
        tab='<table><tr><td>time</td><td>forecast</td><td>actual</td></tr>'+page.text+'</table>'
        tab=tab.replace("&cent;","")
        #print(tab)
        table_MN = pd.read_html(tab,header=0)
     #   print(table_MN[0])
        forecast = table_MN[0]['forecast']
        actual = table_MN[0]['actual']
        newActual[23]=actual[0]
        newForecast[23]=forecast[0]

    #print(newActual)

    
    for i in data['data']:
        if data['data'][i]['actual price']==0 or pd.isna(data['data'][i]['actual price']) or forceupdate==True:
            hour = data['data'][i]['hour']
            if hour < 0:
                continue                    
            if np.isnan(newActual[hour])==False and newActual[hour] is not None:
                print("asdfjkhasdf", newActual[hour])
                data['data'][i]['actual price']=newActual[hour] 
            else:
                data['data'][i]['actual price']=newForecast[hour]
            print(i,newActual[hour], hour)
            data['data'][i]['forecasted price']=newForecast[hour]
            data['data'][i]['Tax and Fees']=0.01783
            data['data'][i]['Comed Fixed']=0.11041



def popDataWithWeather(config, data):
    
    #mgr = owm.weather_manager()
    onecall_request = 'http://api.openweathermap.org/data/3.0/onecall/timemachine?lat=%s&lon=%s&dt=%s&appid=%s'
    
    date= datetime.datetime.fromisoformat(data['date'])
    #we only populate today and before
    if date>datetime.datetime.now():
        return
    #loop through each hour and see if temp is set
    for i in data['data']:
        #if data['data'][i]['temp']==0 or date.date()==datetime.datetime.today().date():
        if data['data'][i]['temp']==0 or date.date()==datetime.datetime.today().date():
            #we're here so temp is missing set the temp or its today
            hour = data['data'][i]['hour']
            if hour < 0:
                continue                    
            working_date = datetime.datetime(
                date.year,
                date.month,
                date.day,
                hour,
                0,
                0,
                0)
            print(working_date)
            print(working_date.timestamp())
            weather = getWeather(config,int(working_date.timestamp()))
            if weather is not None:
                data['data'][i]['temp']=kelvinToFahrenheit(weather['data'][0]['temp'])
    #owm_url = onecall_request % (config['Tesla_Cars']['home_lat'],config['Tesla_Cars']['home_long'],str(int(working_date.timestamp())),owm)
    #print(owm_url)
    #results = requests.get(owm_url)
    #weather_data = print(results.json())
    #print(getWeather(int(working_date.timestamp())))
    #one_call_day_of = mgr.one_call_history(lat=float(config['Tesla_Cars']['home_lat']), lon=float(config['Tesla_Cars']['home_long']), dt=int(working_date.timestamp()))
    
    #print(kelvinToFahrenheit(one_call_day_of.current.temp['temp']))

def add_value(dict_obj, key, value):
    ''' Adds a key-value pair to the dictionary.
        If the key already exists in the dictionary, 
        it will associate multiple values with that 
        key instead of overwritting its value'''
    if key not in dict_obj:
        dict_obj[key] = value
    elif isinstance(dict_obj[key], list):
        dict_obj[key].append(value)
    else:
        dict_obj[key] = [dict_obj[key], value]

def average(lst):
    print(lst)
    if isinstance(lst, float):
        return lst
    return sum(lst) / len(lst)

def findBelow(working_temp, index):
    index=index-1
    while index>=0:
        if working_temp[str(index*10)] >0:
            return working_temp[str(index*10)]
        index=index+1
    return 0

def findAbove(working_temp, index):
    index=index+1
    while index<12:
        if working_temp[str(index*10)] >0:
            return working_temp[str(index*10)]
        index=index+1
    return 0


def calcTempAndTimeImpactOnEnergy(history):
    hourlyTempData = {}
    #loop through everyhour and then loop through everyday and 
    for k in range(24):
        hourlyTempData[str(k)]={}
        for i in history:
            temp = history[i]['data']['hour'+str(k)]['temp']
            if temp!=0:
                energy = history[i]['data']['hour'+str(k)]['energy']
                temp_key = int(int(temp)/10)*10
                add_value(hourlyTempData[str(k)],str(temp_key),energy)
    #loop through again and figure out average and straight line between missing values
    work_temp = {}
    for k in range(24):
        work_temp[str(k)]={}
        #print(str(k))
        #print(work_temp[str(k)])
        #work_temp[str(k)]['10']=0
        #print(work_temp[str(k)])
        
        #print(hourlyTempData[str(k)])
        for i in range(12):
            print(str(i*10))
            if str(i*10) in hourlyTempData[str(k)]:
                print(hourlyTempData[str(k)][str(i*10)])
                work_temp[str(k)][str(i*10)]=average(hourlyTempData[str(k)][str(i*10)])
                #add_value(work_temp[str[k]],str(i*10),1)
                
                #average(hourlyTempData[str(k)][str(i*10)]))
                #finalTempData[str[k]][str(i*10)]=
            else:
                work_temp[str(k)][str(i*10)]=0

                #add_value(work_temp[str[k]],str(i*10),0)
                #finalTempData[str[k]][str(i*10)]=-1
    #print(hourlyTempData['17'])         
    # walk through and find 0's and set to the next one up or linear between 2 numbers
    for k in range(24):
        for i in range(12):
            if work_temp[str(k)][str(i*10)]==0:
                below = findBelow(work_temp[str(k)],i)
                above = findAbove(work_temp[str(k)],i)
                if below==0:
                    below=above
                if above==0:
                    above=below
                #set entry to average of below and above
                work_temp[str(k)][str(i*10)]= (above+below)/2
    
    return work_temp

def saveHistory(history):
        #save history
    with open('history_file.json','w') as history_file:
        json.dump(history,history_file)
    

def getForecast(config):
    owm =config['Credentials']['OMW_key']
    print(owm)
    onecall_request = 'http://api.openweathermap.org/data/3.0/onecall?lat=%s&lon=%s&appid=%s'
    owm_url = onecall_request % (config['Tesla_Cars']['home_lat'],config['Tesla_Cars']['home_long'],owm)
    print(owm_url)
    results = requests.get(owm_url)
    print(results.json())
    return results.json()   

def updateHistoryWithForecast(config, forecast, history):

    for i in forecast:
        dt = datetime.datetime.fromtimestamp(i['dt'])
        
        #check if the day exist...
        if dt.strftime('%Y-%m-%d') not in history:
            createHistory(config,dt,history)
        historyDayData = history[dt.strftime('%Y-%m-%d')]['data']
        print(dt)
        print(dt.hour)
        historyDayData['hour'+str(dt.hour)]['forecasted temp']=kelvinToFahrenheit(i['temp'])


def getForecastTemps(forecast):
    results = {}
    for i in forecast:
        dt = datetime.datetime.fromtimestamp(i['dt'])
        print(dt)
        print(dt.hour)
        results[str(dt.hour)]={'index': (int(kelvinToFahrenheit(i['temp'])/10)*10), 'temp':kelvinToFahrenheit(i['temp'])}
    print(results)
    return results



def calcTodayRemainingEnergyNeed(config,time_energy_lookup, history):
    forecast = getForecast(config)
    now = datetime.datetime.now()
    print(now.hour)
    forecast_temps= getForecastTemps(forecast['hourly'])
    updateHistoryWithForecast(config, forecast['hourly'],history)
    energy_needed = 0 
#lets also update history with the forecasted energy needed
    historyDayData=history[now.strftime('%Y-%m-%d')]['data']
    for i in range(now.hour,24):
        #print(time_energy_lookup[str(i)])
        #print(forecast_temps[str(i)]['index'])
        #print(str(i)+ " hour needs "+str(time_energy_lookup[str(i)][str(forecast_temps[str(i)]['index'])]))
        #print(i)
        energy_needed = energy_needed+ time_energy_lookup[str(i)][str(forecast_temps[str(i)]['index'])]
        historyDayData['hour'+str(i)]['forecasted energy']=time_energy_lookup[str(i)][str(forecast_temps[str(i)]['index'])]
       # print(historyDayData)
       # print (energy_needed)
    return energy_needed

def historyToCSV(history):

    rows = []
    for i in history:
        for k in history[i]['data']:
            working_entry= copy.deepcopy(history[i]['data'][k])
            working_entry['date']=i
            rows.append(working_entry)
    
    headers = [*rows[len(rows)-1]]
    headers.append('battery price')

    print (headers)
    print (rows[len(rows)-1])

    with open('test.csv','w') as csvfile:
        writer = csv.DictWriter(csvfile,fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    

def deleteHistory(config, day_to_delete):
        try:
            with open('history_file.json','r') as history_file:
                history = json.load(history_file)
        except FileNotFoundError:
            history = generateHistory(config,30)
            with open('history_file.json','w') as history_file:
                json.dump(history,history_file)
        print(history.pop(day_to_delete))
        return history

def getHistory(config):
        try:
            with open('history_file.json','r') as history_file:
                history = json.load(history_file)
        except FileNotFoundError:
            history = generateHistory(config,30)
            with open('history_file.json','w') as history_file:
                json.dump(history,history_file)
        
        calcBattsOC(history)
        for i in history:
            popDataWithWeather(config,history[i])
            popDataWithPricing(config,history[i],False)
            popDataWithBattPricing(i,history[i],history)
        return history

if __name__ == "__main__":
        #print(vehicles[0].get_vehicle_data())
    #    vehicles[0].command('STOP_CHARGE')
    

        config=readConfig()
        
        
        #date1_history=getSiteTOUHistory(config,date1,initHourlyHistory())
        #date2_history=getSiteTOUHistory(config,date2,initHourlyHistory())
        #print(date1_history)
        #print(date2_history)
        
        #history_file = open("history_file.json","w")
        #json.dump(generateHistory(config,5),history_file)
        #try:
        #    with open('history_file.json','r') as history_file:
        #        history = json.load(history_file)
        #except FileNotFoundError:
        #    history = generateHistory(config,30)
        #    with open('history_file.json','w') as history_file:
        #        json.dump(history,history_file)
        
        #for i in history:
         #   popDataWithWeather(config,history[i])



        #saveHistory(history)

        
        #save history
        #history = deleteHistory(config,'2022-07-16')
        #saveHistory(history)
        history = getHistory(config)
            
        for i in history:
            history_day=datetime.datetime.strptime(i,'%Y-%m-%d')
            today=datetime.datetime.today()
            today+=datetime.timedelta(days=-15)
            if (history_day>today):
                print(history_day)
        #updateHistory(config,2,history)
#        popDataWithPricing(config,history['2022-06-01'],True)
#        popDataWithBattPricing('2022-06-01',history['2022-06-01'],history)
        #time_energy_lookup = calcTempAndTimeImpactOnEnergy(history)
        #calcTodayRemainingEnergyNeed(config, time_energy_lookup, history)
        #for i in history:
        #    popDataWithWeather(config,history[i])
        #    popDataWithPricing(config,history[i],True)
        #    popDataWithBattPricing(i,history[i],history)
        
        #popDataWithPricing(config,history['2022-07-16'],True)
        #print(history['2022-06-13']['data'])
        #saveHistory(history)

        #historyToCSV(history)

        #updateHistory(config,1,history)
        

        
        
        #time_energy_lookup = calcTempAndTimeImpactOnEnergy(history)
        #calcTodayRemainingEnergyNeed(config, time_energy_lookup, history)
        #updateHistory(config,2,history)
        #popDataWithPricing(config,history['2022-07-01'],True)
        #popDataWithPricing(config,history['2022-07-02'],True)
        #popDataWithPricing(config,history['2022-07-03'],True)
        #popDataWithPricing(config,history['2022-07-16'],True)
 #       popDataWithBattPricing('2022-05-02',history['2022-05-02'],history)


        #print(history['2022-05-02']['data'])
        #saveHistory(history)

        #hourlyAvg = calcAvgEnergyUsageByHour(history)
        #total = 0 
        #for i in hourlyAvg:
        #    total+=hourlyAvg[i]

        #print(hourlyAvg)
        #print(total)

    #battery = tesla.battery_list()
    
    #print(geopy.distance.geodesic(coords_1,coords_2).m)
     # homelink_nearby

