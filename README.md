# TeslaHourlyOptimizer
optimize the solar, powerwall, and vehicle charging based on the current hourly rate from comed


This script rides on the back of teslapy by tdorssers
https://github.com/tdorssers/TeslaPy

you'll need to install a bunch of libraries 

python3 -m pip install teslapy
python3 -m pip install smtplib
python3 -m pip install math
python3 -m pip install pandas
python3 -m pip install numpy
python3 -m pip install requests
python3 -m pip install tkinter
python3 -m pip install matplotlib


to use, create config.txt based off config.txt.sample

the first time you run it, it'll open your browser to tesla.com and to login, it is getting the authentication token; go ahead and login and it'll direct you to a new url
copy that url into the python terminal and it'll create a cache.json file with the authentication token.  after thats happened once, it'll work using that token every time going forward

be default config.txt.sample has send_email_alert = 0, if you want to be emailed everytime the script does something, please update the Email section with an SMTP server you have access to and set send_email alert = 1
it doesn't work with gmail unless you turn off 2 factor authentication.

if you have a tesla car and you want the script to also start charging at the lowest price of the time, set control_cars = 1

if you have an openevse instead of a tesla, set control_openevse = 1 and provide the ip address of the openevse web portal

i've been tinkering with the trigger prices but for sprint of 2022 i've found the settings to be fairly balanced

always charge up everything when price is less than 3 cents
neutral behavior between 3 and 5 cents basically try to keep 50% battery
sell power and use battery when more than 5 cents

also to make this work properly, you have to create a custom time of use rate plan where you have 1-5am is set to ultra off peak with cost of .04 and all other times set to peak with cost of .14

it "tricks" the time of use of peak behavior to sell power instead of use power.  and when we want it to not sell power we switch to self.  the logic is really complex and messy because of all the random tweaking i did

i'll be cleaning it up at some point in the future

