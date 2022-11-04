import json, time
from tkinter import E
import requests
import teslapy
import smtplib
import math

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from unicodedata import normalize
import datetime
import configparser
import geopy.distance
import DataUtils
import MondayUtil
def getLowestFour():
    tomorrow=datetime.datetime.today()
    tomorrow+=datetime.timedelta(days=1)
    today=datetime.datetime.today().strftime('%Y%m%d')
    tomorrow=tomorrow.strftime('%Y%m%d')
    currentHour = int(time.strftime("%H",time.localtime()))
    #we should only be interested in tomorrow if time is after 8pm
    if (currentHour<=20):
        tomorrow=today
    print('right now is ',today, currentHour)
    print('getting forecast price based on',tomorrow)
    URL='https://hourlypricing.comed.com/rrtp/ServletFeed?type=pricingtabledual&date='+tomorrow
    page=requests.get(URL,verify=False)
    # first try tomorrow to see if we have data... if we do then use tomorrow.. else today
    if(len(page.text) <=5):
        URL='https://hourlypricing.comed.com/rrtp/ServletFeed?type=pricingtabledual&date='+today
        page=requests.get(URL,verify=False)
    tab='<table><tr><td>time</td><td>forecast</td><td>actual</td></tr>'+page.text+'</table>'
    tab=tab.replace("&cent;","")
    #print(tab)
    table_MN = pd.read_html(tab,header=0)
    #print(table_MN[0])
    s = table_MN[0]['forecast']
    #print(s.tolist())
    inputlist=s.tolist()
    min_value=min(inputlist)
    min_index=[]

    for k in range(4):
        for i in range(0,len(inputlist)):
            if min_value == inputlist[i]:
                inputlist[i]=99
                min_value=min(inputlist)
                min_index.append(i)
                break
    return min_index , min_value

def startOpenEVSE():
    if config['OpenEVSE']['control_openevse']!='1':
            return
    openevse_ip=config['OpenEVSE']['openevse_ip']
    try:
        print('Start OPENEVSE Charging')
        reset_timer_URL='http://%s/r?rapi=$ST 0 0 0 0' %(openevse_ip)
        start_charge_url='http://%s/r?rapi=$FE' % (openevse_ip)
        requests.get(reset_timer_URL)
        requests.get(start_charge_url)
    except:
        sendMail('N/A','N/A','openevse not responding')

def stopOpenEVSE():
    if config['OpenEVSE']['control_openevse']!='1':
            return
    openevse_ip=config['OpenEVSE']['openevse_ip']
    try:
        print('Stop OPENEVSE Charging')
        min_index, min_value = getLowestFour()
        reset_timer_URL='http://%s/r?rapi=$ST %d 0 %d 0'% (openevse_ip,min(min_index),min(min_index)+3)
        stop_charge_url='http://%s/r?rapi=$FS' % (openevse_ip)
        requests.get(stop_charge_url)
        requests.get(reset_timer_URL)
    except:
        sendMail('N/A','N/A','openevse not responding')

def isTeslaAtHome():
    try:
        if config['Tesla_Cars']['control_cars']!='1':
            return
        teslaUserID=config['Credentials']['TeslaUserID']
        home_lat=float(config['Tesla_Cars']['home_lat'])
        home_long=float(config['Tesla_Cars']['home_long'])
        home = (home_lat,home_long)
        #print(home_lat," ",home_long)
        with teslapy.Tesla(teslaUserID) as tesla:
            vehicles = tesla.vehicle_list()
            print(vehicles[0].get_latest_vehicle_data())

            #print(vehicles[0].get_latest_vehicle_data()['legacy']['drive_state'])
            #if gps data is old then sync and wake up
            if (datetime.datetime.now()-datetime.datetime.fromtimestamp(vehicles[0].get_latest_vehicle_data()['legacy']['drive_state']['gps_as_of'])).total_seconds() > 60*60*3:
                vehicles[0].sync_wake_up()

            
            car_lat = float(vehicles[0].get_vehicle_data()['legacy']['drive_state']['latitude'])
            car_long = float(vehicles[0].get_vehicle_data()['legacy']['drive_state']['longitude'])
            car = (car_lat, car_long)
            print(car)
            print(geopy.distance.geodesic(home,car).m)
            if geopy.distance.geodesic(home,car).m < 50:
                return True
        return False
    except Exception as e:
        print(e)
        return False    

def startTesla():
    if config['Tesla_Cars']['control_cars']!='1':
            return
    if isTeslaAtHome()==False:
        return
    teslaUserID=config['Credentials']['TeslaUserID']
    print('start Tesla Charging')
    try:
        with teslapy.Tesla(teslaUserID) as tesla:
            vehicles = tesla.vehicle_list()
            print("checking connection")
            if vehicles[0].get_vehicle_data()['legacy']['charge_state']['charging_state'] not in ['Charging','Complete','Disconnected']:
                print("connected")
                vehicles[0].sync_wake_up()
                vehicles[0].command('START_CHARGE')
    except Exception as e:
        print(e)
def stopTesla():
    
    if config['Tesla_Cars']['control_cars']!='1':
        return
    if isTeslaAtHome()==False:
        return
    teslaUserID=config['Credentials']['TeslaUserID']
    print('stop Tesla Charging')
    try:
        with teslapy.Tesla(teslaUserID) as tesla:
            vehicles = tesla.vehicle_list()
            print("checking charging state")
            if vehicles[0].get_vehicle_data()['legacy']['charge_state']['charging_state'] in ['Charging']:
                print("currently charging stop it")
                vehicles[0].sync_wake_up()
                vehicles[0].command('STOP_CHARGE')
    except Exception as e:
        print(e)
def sendMail(rate, battery, mode):
    #read config... if send_email_alert isn't 1 then skip and return immediately
    if config['Email']['send_email_alert']!='1':
        return

    if config['Email']['notification_type']=='Monday':
        #logging to monday instead
        MondayUtil.NotificationLogToMonday(config,rate,battery,mode)
        return


    gmail_user = config['Email']['smtp_user']
    gmail_password = config['Email']['smtp_password']

    sent_from = gmail_user
    to = [config['Email']['notify_email']]
    subject = 'Changing Powerwall Mode'
    body = 'Current ComEd Price %s Mode switch to %s battery_back_reserve set to %s' % (rate,mode,battery)
    email_text = """\
From: %s
To: %s
Subject: %s

%s
""" % (sent_from, ", ".join(to), subject, body)
   
    try:
        server = smtplib.SMTP(config['Email']['smtp_server'], config['Email']['smtp_port'])
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(sent_from, to, email_text)
        server.close()

        print('Email sent!')
    except Exception as e:
        print ('Something went wrong...',e)


lastalert=-99.0
highLowCutOff=5.0
stopBatteryCharge=9.0
batteryChargePrice=3.0
currentState=-1

loop_counter=0
hold_hour=-1
currentHour=-1


comEd5Min_URL="https://hourlypricing.comed.com/api?type=5minutefeed"
comEd_URL="https://hourlypricing.comed.com/api?type=currenthouraverage"
print(comEd_URL)

config=MondayUtil.initMonCli()
#print(config)

teslaUserID=config['Credentials']['TeslaUserID']
#print(isTeslaAtHome())

energyForecastUpdated=0
energyForecastTimeStamp=0

TodayRemainingEnergyNeed=0
min_index, min_value=getLowestFour()
print(min_index, min_value) 


while loop_counter<10:
#while 1==0:
    try:
        min_index, min_value=getLowestFour()
        print(min_index, min_value)  
        latestUTC = 0
        latestPrice = 0.0
        currentBatteryStatus = ''
        sleptTime=0
        results = 0
        sticky_backup_reserve=0     
        #try to get comed results... if comed service is down.. keep waiting 
        while results == 0:
            try:
                results= requests.get(comEd_URL,verify=False)
                results5Min = requests.get(comEd5Min_URL,verify=False)
            except Exception as e:
                print("comed choked sleeping for 30 seconds and trying again")
                print(e)
                sleptTime+=30
                time.sleep(30)
        jsonResponse=results.json()
        jsonResponse5Min=results5Min.json()
        print("comed result: ",jsonResponse)
        print("comed 5 min results:", jsonResponse5Min)
        #in case we slept more than 300 seconds we want to make sure we just pickup in the next 5 minute cycle
        sleptTime = sleptTime % 300    

        #get the current solar status
        with teslapy.Tesla(teslaUserID) as tesla:
            battery = tesla.battery_list()
            currentBatteryStatus=battery[0].get_battery_data()      
            total_pack_energy=float(currentBatteryStatus['total_pack_energy'])
            while total_pack_energy < 1000:
                currentBatteryStatus = battery[0].get_battery_data()
                total_pack_energy=float(currentBatteryStatus['total_pack_energy'])
                if total_pack_energy < 1000:
                    time.sleep(30)

        #print(currentBatteryStatus)
        solar_power=int(currentBatteryStatus['power_reading'][0]['solar_power'])
        battery_power=int(currentBatteryStatus['power_reading'][0]['battery_power'])
        grid_power=int(currentBatteryStatus['power_reading'][0]['grid_power'])
        load_power=int(currentBatteryStatus['power_reading'][0]['load_power'])    
        #percent_charged=float(currentBatteryStatus['percentage_charged'])
        energy_left=float(currentBatteryStatus['energy_left'])
        total_pack_energy=float(currentBatteryStatus['total_pack_energy'])
        percent_charged= int((energy_left/total_pack_energy) *100)
        
        
        time_to_charge = (total_pack_energy-energy_left)/15000
        lastHour=currentHour
        currentHour = int(time.strftime("%H",time.localtime()))
        currentMin = int(time.strftime("%M",time.localtime()))

        
        
        #if we transitioned to high anytime within the hour, then we assume the rest of the hour must be bouncing around high so we hold until the top of the next hour

        print("current Hour",currentHour," current min", currentMin)
        print("time to charge", time_to_charge, "hrs")
        
        if lastHour!=currentHour:
            #we're here so we're at the top of the hour.. lets get latest forecasts and save it to history
            history = DataUtils.getHistory(config)
            DataUtils.popDataWithPricing(config,history[datetime.datetime.today().date().strftime('%Y-%m-%d')],True)
            time_energy_lookup = DataUtils.calcTempAndTimeImpactOnEnergy(history)
            TodayRemainingEnergyNeed=DataUtils.calcTodayRemainingEnergyNeed(config, time_energy_lookup, history)
            energyForecastTimeStamp=datetime.datetime.now().timestamp()
            DataUtils.updateHistory(config,0,history)
            print('updating history',history[datetime.datetime.today().date().strftime('%Y-%m-%d')]['data'])
            DataUtils.saveHistory(history)
            MondayUtil.UpdateSyncToMonday(config,history[datetime.datetime.today().date().strftime('%Y-%m-%d')])
            MondayUtil.UpdateSavingsChartingBaord(config,datetime.datetime.today().date().strftime('%Y-%m-%d'))
        print("forecasted energy need", TodayRemainingEnergyNeed, "current battery SOC",energy_left)


        for i in jsonResponse:
            millisUTC=i['millisUTC']
            price=i['price']
            if int(millisUTC) > latestUTC:
                latestUTC=int(millisUTC)
                latestPrice=float(price)
        
        latest5MinUTC = 0
        latest5MinPrice = 0.0
        for i in jsonResponse5Min:
            millisUTC=i['millisUTC']
            fiveMinPrice=i['price']
            if int(millisUTC) > latest5MinUTC:
                latest5MinUTC=int(millisUTC)
                latest5MinPrice=float(fiveMinPrice)


        if (currentHour not in min_index or latestPrice>stopBatteryCharge) and currentState==0 and latestPrice>min(lastalert,min_value):
            print("resetting currentState")
            currentState=-1
        
        runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,-1,'unknown',TodayRemainingEnergyNeed)
        MondayUtil.runLogToMonday(config,runLog)

    #battery if we are ever in negative pricing territory and its been that way for the first 15 min of the hour,  level is < 80% and we are betwee 2 and 5am charge regardless of price  1==0 never happens so we don't go into self state
        if (latestPrice<0 and currentMin>15 and currentState!=0) or (percent_charged < 99 and (currentHour in min_index or latestPrice<min(4,min_value)) and currentState!=0 and latestPrice <stopBatteryCharge):
                print("alert transition to force charge ",latestUTC,":",latestPrice)
                with teslapy.Tesla(teslaUserID) as tesla:
                    battery = tesla.battery_list()
                    battery[0].set_backup_reserve_percent(100)
                    battery[0].set_operation('autonomous')
                    print('setting charge battery to self backup_reserve_percent to ',battery[0].get_battery_data()['backup']['backup_reserve_percent'])
                    sticky_backup_reserve = 100
                    sendMail(latestPrice,battery[0].get_battery_data()['backup']['backup_reserve_percent'],'force self charging')
                #payload = {"backup_reserve_percent": 100}
                #requests.post(webhook_URL,json=payload)
                runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,100,'autonomous',TodayRemainingEnergyNeed)
                MondayUtil.runLogToMonday(config,runLog)
                lastalert=latestPrice
                hold_hour=-1
                currentState=0
                startOpenEVSE()
                startTesla()
    # if price is high and we don't have significant solar coming in (due to sun down or cloudy)
        elif latestPrice > highLowCutOff and solar_power<=100 and (currentState!=1 and currentState!=0):
            print("alert transition to high self",latestUTC,":",latestPrice)
            with teslapy.Tesla(teslaUserID) as tesla:
                battery = tesla.battery_list()
                # we force set to self since there's no solar anyway this is safer
                battery[0].set_operation('self_consumption')
                battery[0].set_backup_reserve_percent(0)
                sticky_backup_reserve=0
                print('setting backup_reserve_percent to ',battery[0].get_battery_data()['backup']['backup_reserve_percent'])
                sendMail(latestPrice,battery[0].get_battery_data()['backup']['backup_reserve_percent'],'high self')
                hold_hour=currentHour
            #requests.post(webhook_URL,json=payload)
            lastalert=latestPrice
            currentState=1
            runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,0,'self_consumption',TodayRemainingEnergyNeed)
            MondayUtil.runLogToMonday(config,runLog)
            stopOpenEVSE()
            stopTesla()
        #if price is high and we do have solar coming in then we need to use battery we don't want to sell solar right now because net metering ain't working
        elif latestPrice > highLowCutOff and solar_power>100 and ((currentState!=2 and currentState!=0) or energyForecastTimeStamp>energyForecastUpdated): 
            print("alert price is high... and we have solar... assumption is price is higher later in the day so we should use our solar and recharge not a always true assumption ",latestUTC,":",latestPrice)
            with teslapy.Tesla(teslaUserID) as tesla:
                battery = tesla.battery_list()
                # we force set to autonomous because we want to incent sending power to the grid as price is high
                #api funkiness... gotta keep looping until total is a very large positive it should be 40,000
                tmp_percentage_charged = 0.0
                total=0.0
                while total < 1000:
                    currentBatt = battery[0].get_battery_data()
                    total=currentBatt['total_pack_energy']
                    left=currentBatt['energy_left']
                    tmp_percentage_charged= int((left/total) *100)
                    if total < 1000:
                        sleep(30)
                        sleptTime+=30

                total=currentBatt['total_pack_energy']
                left=currentBatt['energy_left']

                tmp_percentage_charged= int((left/total) *100)
                targetReserve = int((TodayRemainingEnergyNeed / total) *100)

                #peak solar is around 10-11am... we should be making decision around this time
                #we only go into autonomoous if we have enough battery to cover the day.. else we go into self
                energyForecastUpdated=energyForecastTimeStamp
                operation='autonomous'
                if currentHour>9 and left>=TodayRemainingEnergyNeed:
                    print( "we have enough battery to run through the day setting to autonomous",)
                    battery[0].set_operation('autonomous')
                else:
                    print("we don't have enough battery to run through the end of the day so setting to self")
                    operation='self_consumption'
                    battery[0].set_operation('self_consumption')
                #we currently still don't reserve the battery... but we need to look at forecast price action later to determine if we should save battery now or use it... thats logic for another day
                battery[0].set_backup_reserve_percent(1)
                sticky_backup_reserve=1
                print('setting to autonomous and backup_reserve_percent to ',battery[0].get_battery_data()['backup']['backup_reserve_percent'])
                # we sleep for 30 seconds and check what the ROI model is doing.  the reason why is because ROI model does weird things like charge from grid even though the price is high
                sendMail(latestPrice,battery[0].get_battery_data()['backup']['backup_reserve_percent'],'high autonomous')
                time.sleep(30)
                sleptTime=30
                battery_power=float(battery[0].get_battery_data()['power_reading'][0]['battery_power'])
                solar_power=float(battery[0].get_battery_data()['power_reading'][0]['solar_power'])
                grid_power=float(battery[0].get_battery_data()['power_reading'][0]['grid_power'])
                if battery_power <= -500 and grid_power>=(-1*battery_power*.9):
                    #autonomous ROI model is doing something weird since after 30 seconds battery should be positive power so forcing to operation mode of self 
                    print(battery[0].get_battery_data())
                    print('setting to self and backup_reserve_percent to ',battery[0].get_battery_data()['backup']['backup_reserve_percent'])
                    battery[0].set_operation('self_consumption')
                    sendMail(latestPrice,battery[0].get_battery_data()['backup']['backup_reserve_percent'],'high self')
            #requests.post(webhook_URL,json=payload)
            hold_hour=currentHour
            lastalert=latestPrice
            currentState=2
            runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,sticky_backup_reserve,operation,TodayRemainingEnergyNeed)
            MondayUtil.runLogToMonday(config,runLog)
            stopOpenEVSE()
            stopTesla()
        ##if the current price is midlevel.. lower than high price but still too expensive to charge.  we want to take the power from the grid while preserving battery capacity we don't care for solar it can charge not charge it doesn't matter
        elif latestPrice <= highLowCutOff and latestPrice>= batteryChargePrice and currentHour!=hold_hour and (currentState!=3 and currentState!=0):
                print("alert transition to low ",latestUTC,":",latestPrice)
                with teslapy.Tesla(teslaUserID) as tesla:
                    battery = tesla.battery_list()
                    #api funkiness... gotta keep looping until total is a very large positive it should be 40,000
                    tmp_percentage_charged = 0.0
                    total=0.0
                    while total < 1000:
                        currentBatt = battery[0].get_battery_data()
                        total=currentBatt['total_pack_energy']
                        left=currentBatt['energy_left']
                        tmp_percentage_charged= int((left/total) *100)
                        if total < 1000:
                            sleep(30)
                            sleptTime+=30
                    battery[0].set_operation('self_consumption')
                    #we're doing min(50,tmp_percentage_charged) because in the event that solar has been keeping to super high and battery is already at 100, we rather draw down the battery instead of taking from the grid since the price is only mid level 
                    battery[0].set_backup_reserve_percent(min(50,tmp_percentage_charged))
                    sticky_backup_reserve=tmp_percentage_charged
                    print('setting to self backup_reserve_percent to ',battery[0].get_battery_data()['backup']['backup_reserve_percent'])
                    sendMail(latestPrice,battery[0].get_battery_data()['backup']['backup_reserve_percent'],'low self')
                    #print('low self battery status', battery[0].get_battery_data())
                    print('success')
                    #force set it again just for fun
                    #battery[0].set_backup_reserve_percent(tmp_percentage_charged)
                    
                #payload = {"backup_reserve_percent": 100}
                #requests.post(webhook_URL,json=payload)
                lastalert=latestPrice
                #setting hold_hour to -1 so that it doesn't enforce a hold once we enter lower state
                hold_hour=-1 
                currentState=3
                runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,sticky_backup_reserve,'self_consumption',TodayRemainingEnergyNeed)
                MondayUtil.runLogToMonday(config,runLog)
                stopOpenEVSE()
                stopTesla()
        #if the current price at the half hour mark is below batteryChargePrice then we want to take from grid
        elif latestPrice <= batteryChargePrice and currentHour!=hold_hour and currentMin > 30 and (currentState!=4 and currentState!=0):
                print("alert transition to last half hour below battery charge price ",latestUTC,":",latestPrice)
                with teslapy.Tesla(teslaUserID) as tesla:
                    battery = tesla.battery_list()
                    battery[0].set_operation('autonomous')
                    battery[0].set_backup_reserve_percent(100)
                    sticky_backup_reserve=100
                    print('setting to charge battery and autonomous backup_reserve_percent to ',battery[0].get_battery_data()['backup']['backup_reserve_percent'])
                    sendMail(latestPrice,battery[0].get_battery_data()['backup']['backup_reserve_percent'],'low self charging')
                #payload = {"backup_reserve_percent": 100}
                #requests.post(webhook_URL,json=payload)
                lastalert=latestPrice
                #setting hold_hour to -1 so that it doesn't enforce a hold once we enter lower state
                hold_hour=-1
                currentState=4
                runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,100,'self_consumption',TodayRemainingEnergyNeed)
                MondayUtil.runLogToMonday(config,runLog)
                startOpenEVSE()
                startTesla()
        elif currentState==-1 or (currentState==4 and currentMin<=30):
                print("alert transition to default of self 20 because price is super low but we're in the first half of the hour so we just don't trust it ",latestUTC,":",latestPrice)
                with teslapy.Tesla(teslaUserID) as tesla:
                    battery = tesla.battery_list()
                    battery[0].set_operation('self_consumption')
                    battery[0].set_backup_reserve_percent(20)
                    sticky_backup_reserve=100
                    print('setting to charge battery and self backup_reserve_percent to ',battery[0].get_battery_data()['backup']['backup_reserve_percent'])
                    sendMail(latestPrice,battery[0].get_battery_data()['backup']['backup_reserve_percent'],'low self charging')
                #payload = {"backup_reserve_percent": 100}
                #requests.post(webhook_URL,json=payload)
                lastalert=latestPrice
                #setting hold_hour to -1 so that it doesn't enforce a hold once we enter lower state
                hold_hour=-1
                currentState=5
                runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,20,'self_consumption',TodayRemainingEnergyNeed)
                MondayUtil.runLogToMonday(config,runLog)
                stopOpenEVSE()
                stopTesla()
        else:
            print ("no change current state:",currentState," current price:",latestPrice, "lastAlert Price:", lastalert," hold hour:",hold_hour," current_hour",currentHour)
            runLog=MondayUtil.initRunLog(math.trunc(datetime.datetime.now().timestamp()),currentHour,currentMin,energy_left,time_to_charge,solar_power,battery_power,grid_power,load_power,lastalert,min(min_index),min_value,latestPrice,latest5MinPrice,currentState,-1,'no_change',TodayRemainingEnergyNeed)
            MondayUtil.runLogToMonday(config,runLog)
        
        currentMin = int(time.strftime("%M",time.localtime()))
        if currentMin % 5 != 0:
            sleptTime=((currentMin % 5)*60)
            print ("not on the 5 minute mark: current min is ", currentMin," adjusting sleep by ",sleptTime )
        time.sleep(300-sleptTime)
    except Exception as e:
        print("tesla choked sleeping for 1 minute  and trying again")
        print(e)
        time.sleep(60)
