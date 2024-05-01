#CIT381 Final Project Implementation
#Team 1:  Hassan Alsaffar, Michael Clark, Zach Halcomb, Jason Sand
 
#import GPIO modules for Motion Sensor, Buttons, LEDs, relay, and the Door Lock Servo to function
from gpiozero import MotionSensor, Button, LED, Servo
#import modules used to access the camera and display a preview
from picamera2 import Picamera2, Preview
#import modules used to build and send the Email message
import smtplib, ssl
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
#import the LCD Driver from file (found on Canvas)
import I2C_LCD_driver
#import os module to invoke CLI
import os
#import time module to invoke current time and to delay code
import time
#import multithreading to run two functions simutaniously; used for door cycle
import threading
#import datetime and timezone to obtain the current time in timezone (EST default)
from pytz import timezone
import datetime
#import PiGPIOFactory to reduce Servo stutter
from gpiozero.pins.pigpio import PiGPIOFactory
factory = PiGPIOFactory()

# Define gpio pins
#Define the motion sensor used to detect movement
pir = MotionSensor(16)                             #GPIO 16; ensure that the detection time set on the actual device has been increased and not at the lowest value!
#Define the Servo used to control the door lock
door_lock = Servo(19, pin_factory=factory)         #GPIO 19
#Define LEDs
green_led = LED(5, active_high = False)            #GPIO 05
yellow_led = LED(6, active_high = False)           #GPIO 06
red_led = LED(13, active_high = False)             #GPIO 13
#Define the Pin to control the relay    
Relay = LED(12) #active_high = False)               #GPIO 12
#Define button PINS
button1 = Button(17, bounce_time=0.25) #input 1,2   GPIO 17
button2 = Button(22, bounce_time=0.25) #input 3,4   GPIO 22
button3 = Button(27, bounce_time=0.25) #input 5,6   GPIO 27
button4 = Button(18, bounce_time=0.25) #input 7,8   GPIO 18
button5 = Button(23, bounce_time=0.25) #input 9,0   GPIO 23

#setup the camera with Picamera2 and configure input resolution
picam2 = Picamera2()    #Documentation found here: https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf
camera_config = picam2.create_video_configuration(main={"size": (2048, 1536)})
picam2.configure(camera_config) #apply the configuration

#start the camera preview
picam2.start_preview(Preview.QTGL, width=1280, height=720)  #1280 x 720 fills the entire resolution of the touchscreen

#initialize the LCD using Driver
lcDisplay = I2C_LCD_driver.lcd()

# Turn all LEDs off
green_led.off()
yellow_led.off()
red_led.off()

#Clear the Display at start
lcDisplay.lcd_clear()

#door starts as locked, set variables to reflect this
lockState = True    #the state of the lock
doDoorCycle = True  #if the door cycle is ongoing or not

#Configurable Parameters
#set the correct PIN using a list, and PIN length using a variable
cPIN = [1, 2, 3, 4]     #PIN: 1234
lenPIN = 4              #PIN length: 4
# Email Information
port = 587  #the port used to send Email; starttls  
sender_email = "z60371263@gmail.com" #the email of the sender that logs into the smtp server
password = "xrmq xceq kdsh qcjp "    #the password of the sender email
receiver_email = "zachhalcomb@protonmail.com" #the email address that will be recieving the message

#build the Email message to be sent when motion is detected
Subject = 'Someone was detected at your door!' #message subject
Body = 'An image was captured. See the Attachments for Details.' #message body
Filename = 'test' #the name of the file that is captured by piCamera2, line: x

#create lists to split odd/even numbers to be called when the corresponding button is pushed. There is a probably a better way to do this.
firstEntry = [1, 3, 5, 7, 9] #first time
secEntry = [2, 4, 6, 8, 0]  #second time
#set an empty list to fill when a PIN number is input
iPIN = []

#create an empty string for outputing PIN numbers to LCD
output_string = ""

#set variable to count the number of PIN inputs taken
tInput = 0
#set variable to determine if the first email should be sent right away instead of waiting 60 seconds
startEmail = 0
#set variable to determine when the last email time was
lastEmailTime = time.time()

#set the timezone
tz = timezone('EST')

#Function used to display text onto the LCD screen; takes input and which row to display in
def displayLCD(query,pos):
    #Display query onto the LCD
    if pos == 1: # First row
        lcDisplay.lcd_display_string(query, 1,0)
    else: #Second row
        lcDisplay.lcd_display_string(query, 2,0)

#Function that takes a Subject, Body, and Filename to send an Email with a picture attached, 
#referenced: https://realpython.com/python-send-email/#adding-attachments-using-the-email-package
def sendMail(Subject, Body, Filename):
    # Email Information 
    port = 587 # For starttls; the port to use
    sender_email = "z60371263@gmail.com"  #smtp address of Sender
    receiver_email = "zachhalcomb@protonmail.com"  #Recievers address
    password = "xrmq xceq kdsh qcjp "   #The password for the smtp server

    #Setup Email Parameters
    msg = MIMEMultipart("alternative")
    msg['From'] = sender_email #Sender 
    msg['To'] = receiver_email #Reciever
    msg['Subject'] = Subject    #Add Subject to Email
    msg.attach(MIMEText(Body, "plain"))    # Add Body to email

    #check if null is passed to skip sending a picture attachment
    if Filename != 'null':
        #get the current directory
        currentDir = os.getcwd()
        #locate the image
        filepath = currentDir + '/' + Filename + '.jpg' 
        #open the specified file
        with open(filepath, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        #Encode file in ASCII characters
        encoders.encode_base64(part)    
        #Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {filepath}",
        )
        #Add attachment to message 
        msg.attach(part)

    # Send the email
    context = ssl.create_default_context()
    with smtplib.SMTP('smtp.gmail.com', port) as server:    #the smtp server
        server.starttls(context=context)
        server.login(sender_email, password)    #login to the server
        server.sendmail(sender_email, receiver_email, msg.as_string())  #send the email
        print("Email Sent, Details: " + Subject)    #output to console what was done

#Function called when motion is detected
def doMotion():
    #Notify console and LCD that motion was detected
    print("Motion Detected")
    displayLCD('Recording!', 2) #row 2

    #start the camera feed
    picam2.start()  

    #obtain the current time in the specified timezone
    current_time = datetime.datetime.now(tz)
    #obtain only the current hour
    current_time = current_time.hour
    current_time = 20   #uncomment this to test Relay Function
    #Determine if it is night
    if current_time in range(20,24):    #8PM to 11PM
        #Trigger the Relay. When the relay is powered, it will turn on the Blue LED that is supposed to represent a light fixture on the porch
        Relay.on()
    elif current_time in range(0,9):    #12AM to 8AM
        #Trigger the Relay.
        Relay.on()
    #if else, pass because it is currently day
    else:
        pass

    #light the Yellow LED to notify camera is recording
    yellow_led.on()

    #take a picture and save it to 'test.jpg'
    picam2.capture_file("test.jpg")
    print("Captured a new picture")

    #send the picture with email
    global startEmail  #access global variables to determine method and to update them
    global lastEmailTime

    #send the first email by skipping the 60 second wait (Disney Fastpass)
    if startEmail == 0: #if an email has yet been sent when first started 
        startEmail = 1  #set global value to 1 to prevent doing this again
        #send the first Email
        sendMail(Subject, Body, Filename)
        #Notify that the first email has been sent
        print("Sent first email")

    #send an email when 1 minute has elapsed
    else:
        #obtain the current time
        currentEmailTime = time.time()
        #compare the current time to the last time an email was sent to determine if 1 minute has passed
        if currentEmailTime - lastEmailTime >= 60:
            #send the Email
            sendMail(Subject, Body, Filename)
            #set the last time an email was sent to the current time
            lastEmailTime = currentEmailTime

#Function used to freeze the camera feed and turn the relay off when motion is no longer detected
def noMotion():
    #freeze the camera feed
    picam2.stop()
    #notify console that motion is no longer detected
    print('No motion')
    displayLCD("           ", 2) #clear row 2 on LCD
    #Turn Relay off
    Relay.off()
    #turn yellow LED off
    yellow_led.off()


#Function used to Cycle Unlocking and Locking the Door
def doorCycle():
    if lockState == True: #if the door is locked
        #unlock the door by moving servo to maximum position
        door_lock.max()

        #display that the door is unlocking
        displayLCD("Unlocking Door!",1)
        #display for 1 second
        time.sleep(1)

        #Build an Email message to notify that the door was unlocked by the PIN
        Subject = "Your door was unlocked!"
        Body = "Your door was unlocked because the correct PIN was entered"
        Filename = "null" #set to null to avoid sending picture
        #send the Email
        sendMail(Subject, Body, Filename)

        #sleep function for 1 minute to ensure that the door has been closed
        displayLCD("waiting        ",1)
        time.sleep(60)

        #relock the door after minute has passed
        door_lock.min()
        #display that the door is locking
        displayLCD("Locking Door!",1)
        #display for 1 second
        time.sleep(1)

        #Build another Email message to notify door was locked back
        Subject = "The door was locked back!"
        Body = "Your door was locked back after the set inactive period"
        #send the second Email
        sendMail(Subject, Body, Filename)

        #sleep again
        time.sleep(1)
        #change doDoorCycle back to True
        global doDoorCycle
        doDoorCycle = True

        #clear the top portion from theLCD
        displayLCD("                 ", 1)   
        #the green LED will be on during the door cycle, so turn it off after it has completed if it already hasn't
        green_led.off()


#Function called when a button is pressed, pass the corresponding button and the corresponding number in the list(s)
def button_Press(button,number):
    #change the tInput variable globaly
    global tInput

    #turn both LEDS off since new input is being taken
    red_led.off()
    green_led.off()

    timeout = 0.7 #timeout of 0.5 seconds (how much time is allowed for button to be pressed again)
    #obtain the current time and set it to a variable
    start_time = time.time()
    #since the button has been pressed, it defaults to the first (odd) value
    pinVal = firstEntry[number]
    #sleep for 1/4 second, don't remove it breaks the code for some reason
    time.sleep(0.25)

    #for 0.5 seconds, allow the button to be pressed again
    while time.time() - start_time < timeout:   #When the difference between current time and set time is still less than the alloted timeout given
        #if the button is pressed again
        if button.is_pressed:
            #set the value to the second list
            pinVal = secEntry[number]

    #if the PIN is still below the given length
    if tInput < 4:
        #increment the number of inputs by 1
        tInput = tInput + 1
        #append the input number to the input list
        iPIN.append(pinVal)

    #return the number
    return pinVal

#Function used to clear PIN input and start over
def resetVar():
    global tInput
    global iPIN
    global output_string
    #reset all variables to try again
    tInput = 0  #times input
    iPIN.clear() #Clear the PIN input
    output_string = ""  #the output string to the LCD

#When motion is detected, call the doMotion function to record, take picture, and send Email message
pir.when_motion = doMotion
#When motion is no longer detected, freeze the camera feed
pir.when_no_motion = noMotion

#Main Code Loop
try:
    while True:
        #if last two buttons are pressed together, reset PIN entry
        if button1.value == 1 & button2.value == 1:
            resetVar()
            displayLCD("           ", 1)    #Clear the Top display

        else:
            #scan for when each button is pressed
            if button1.value == 1:              #Button 1
                x = button_Press(button1, 0)    #call the button_Press function to save input number to a variable
                output_string += str(x) + " "   #append the number to output string
                displayLCD(output_string,1)       #display output string onto the LCD
            #Button 2
            if button2.value == 1:              
                x = button_Press(button2, 1)    #Ditto 
                output_string += str(x) + " " 
                displayLCD(output_string,1)
            #Button 3
            if button3.value == 1:              
                x = button_Press(button3, 2)
                output_string += str(x) + " " 
                displayLCD(output_string,1)    
            #Button 4
            if button4.value == 1:              
                x = button_Press(button4, 3)
                output_string += str(x) + " " 
                displayLCD(output_string,1)    
            #Button 5
            if button5.value == 1:              
                x = button_Press(button5, 4)
                output_string += str(x) + " " 
                displayLCD(output_string,1)


        #if the number of inputs equals the set PIN length
        if tInput == lenPIN:
            #sleep for 1 sec. to display the last input number onto the LCD
            time.sleep(1)
            #check if input PIN is equal to set PIN
            if iPIN == cPIN: #equal
                    #Input PIN is valid
                    displayLCD("PIN Valid",1)
                    time.sleep(1)

                    #light the Green LED
                    green_led.on()
                
                    #Unlock the door
                    if doDoorCycle == True:
                        doDoorCycle = False
                        threading.Thread(target=doorCycle).start()
            else:
                #invalid
                displayLCD("PIN Invalid",1)
                #light the RED LED
                red_led.on()
            #sleep for 1 sec. to display feedback
            time.sleep(1)

            #Call function used to reset PIN variables
            resetVar()
            
            #if the door cycle is currently not occuring (maintain the "Door Cycle" phrase on the LCD)
            if doDoorCycle == True:
                displayLCD("           ", 1)   #clear the top portion from theLCD
        
        #sleep code for 1/4 second
        time.sleep(0.25)
except Exception as error:
    print("Code Exited with Error: " + error)

finally:
    lcDisplay.lcd_clear()
    green_led.off
    yellow_led.off
    red_led.off