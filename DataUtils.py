from ast import dump
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

def readConfig():
   config = configparser.ConfigParser()
   config.read('config.txt')
   return config

def initHourlyHistory():
    hourly_history={}
    for k in range(24):
        hourly_history['hour'+str(k)]={'hour':0,'energy':0,'solar':0 ,'grid':0,'battery':0, 'temp':0,'forecasted energy':0, 'forecasted temp':0, 'actual price':0,'forecasted price':0}
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
    if (str(dt) not in w_hist or datetime.datetime.fromtimestamp(dt).date()==datetime.datetime.today().date()):
        owm =config['Credentials']['OMW_key']
        print(owm)
        onecall_request = 'http://api.openweathermap.org/data/3.0/onecall/timemachine?lat=%s&lon=%s&dt=%s&appid=%s'
        owm_url = onecall_request % (config['Tesla_Cars']['home_lat'],config['Tesla_Cars']['home_long'],str(int(dt)),owm)
        print(owm_url)
        results = requests.get(owm_url)
        print(results.json())
        w_hist[str(dt)]=results.json()
        with open('weather_history.json','w') as weather_history_file:
            json.dump(w_hist,weather_history_file)
    return w_hist[str(dt)]
 

def popDataWithWeather(config, data):
    
    #mgr = owm.weather_manager()
    onecall_request = 'http://api.openweathermap.org/data/3.0/onecall/timemachine?lat=%s&lon=%s&dt=%s&appid=%s'
    
    date= datetime.datetime.fromisoformat(data['date'])
    #we only populate today and before
    if date>datetime.datetime.now():
        return
    #loop through each hour and see if temp is set
    for i in data['data']:
        if data['data'][i]['temp']==0 or date.date()==datetime.datetime.today().date():
            #we're here so temp is missing set the temp or its today
            hour = data['data'][i]['hour']
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
    for i in range(now.hour,23):
        print(time_energy_lookup[str(i)])
        print(forecast_temps[str(i)]['index'])
        print(str(i)+ " hour needs "+str(time_energy_lookup[str(i)][str(forecast_temps[str(i)]['index'])]))
        print(i)
        energy_needed = energy_needed+ time_energy_lookup[str(i)][str(forecast_temps[str(i)]['index'])]
        historyDayData['hour'+str(i)]['forecasted energy']=time_energy_lookup[str(i)][str(forecast_temps[str(i)]['index'])]
        print(historyDayData)
        print (energy_needed)
    return energy_needed

def getHistory(config):
        try:
            with open('history_file.json','r') as history_file:
                history = json.load(history_file)
        except FileNotFoundError:
            history = generateHistory(config,30)
            with open('history_file.json','w') as history_file:
                json.dump(history,history_file)
        
        for i in history:
            popDataWithWeather(config,history[i])
        return history

if __name__ == "__main__":
    with teslapy.Tesla('jhu321@hotmail.com') as tesla:
        vehicles = tesla.vehicle_list()
        print(vehicles[0].get_vehicle_data()['charge_state']['charging_state'])
        #print(vehicles[0].get_vehicle_data())
    #    vehicles[0].command('STOP_CHARGE')
    

        latitude1 = 41.97377
        longitude1= -87.75939

        latitude2= 41.973828
        longitude2= -87.759414

        coords_1 = (latitude1, longitude1)
        coords_2 = (latitude2, longitude2)
        config=readConfig()
        
        date1 = datetime.datetime(
        2022,
        5,
        23,
        0,
        0,
        0,
        0
        )
        date2 = datetime.datetime(
        2022,
        5,
        25,
        0,
        0,
        0,
        0
        )
        
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



        #updateHistory(config,31,history)
        #saveHistory(history)

        
        #save history
        history = getHistory(config)
        
        
        
        
        #time_energy_lookup = calcTempAndTimeImpactOnEnergy(history)
        #calcTodayRemainingEnergyNeed(config, time_energy_lookup, history)
        #updateHistory(config,2,history)
        #print(history['2022-05-30']['data'])
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

