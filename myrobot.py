#!/usr/bin/python
#-*- coding: utf-8 -*-
import os
from importlib import import_module
from flask import Flask, render_template, Response
from flask import render_template
from flask import request
from flask import abort, redirect, url_for
from flask import render_template
from flask import session, escape
from flask import g, flash
from flask import send_from_directory
from flask import jsonify
import json
from time import sleep 
import io
from camera_pi import Camera
import logging
from threading import Condition 
from camera_pi import Camera


import threading


HEADLIGHT = 3
L_LED = 29
R_LED = 31
B_MOTOR_A = 35
B_MOTOR_B = 37
F_MOTOR_A = 38
F_MOTOR_B = 40


def init_gpio():
    try:
		print("initialize gpio... ")
		GPIO.cleanup()
		GPIO.setmode( GPIO.BOARD )

		GPIO.setup( HEADLIGHT, GPIO.OUT )
		GPIO.setup( L_LED, GPIO.OUT )
		GPIO.setup( R_LED, GPIO.OUT )
		GPIO.setup( B_MOTOR_A, GPIO.OUT )
		GPIO.setup( B_MOTOR_B, GPIO.OUT )
		GPIO.setup( F_MOTOR_A, GPIO.OUT )
		GPIO.setup( F_MOTOR_B, GPIO.OUT )
    except:
        pass
    pass


try:
    import RPi.GPIO as GPIO
except:
    print("not found gpio library")

import time
import threading
from threading import Timer
import datetime


app = Flask( __name__ )
app.debug = True
app.config.from_object(__name__)


class Ubaba:
    def __init__(self):
        
        print('''
        --- UBABA Initialize... ---
        
        ''')
        self.duty = 0
        self.freq = 100

        self.acceleration = False   # 가속중인가? 
        self.brake = False          # 브레이크
        self.gear = 0               # 기어(주행방향) -1: 후진 0:정지 1:1단 2:2단 3:3단 4:4단 5:5단 
        self.acceleration_rate = 4  # 2 Duty/sec 초당 1duty씩 증가 
        self.reduction_rate = 2     # 1 Duty/sec 초당 2duty씩 감소 
        self.direction = 0          # 조향방향. 0:center 1:left 2:right

        self.current_duty = 0   # 현재속도
        self.target_duty = 0        # 목표속도. 가속중이라면 기어에 해당하는 최고속도, 감속중이라면 0

        self.gear_duty = { -1:60, 0:0, 1:50, 2:60, 3:70, 4:80, 5:90 }   # 기어별 목표속도


        self.F_MOTOR_A = 38
        self.F_MOTOR_B = 40
        self.B_MOTOR_A = 37
        self.B_MOTOR_B = 35
        self.F_LED = 3
     
        self.f_led_thread_running = False


        GPIO.cleanup()
        GPIO.setmode( GPIO.BOARD )
        GPIO.setup( self.F_MOTOR_A, GPIO.OUT )
        GPIO.setup( self.F_MOTOR_B, GPIO.OUT )
        GPIO.setup( self.F_LED, GPIO.OUT )
        GPIO.output( self.F_MOTOR_A, False )
        GPIO.output( self.F_MOTOR_B, False )
        GPIO.output( self.F_LED, True )

        GPIO.setup( self.B_MOTOR_A, GPIO.OUT )
        GPIO.setup( self.B_MOTOR_B, GPIO.OUT )
        GPIO.output( self.B_MOTOR_A, False )
        GPIO.output( self.B_MOTOR_B, False )

        self.pwm_F = GPIO.PWM( self.F_MOTOR_B, 10)
        self.pwm_B = GPIO.PWM( self.F_MOTOR_A, 10)

        self.pwm_L = GPIO.PWM(self.B_MOTOR_A, 60)
        self.pwm_R = GPIO.PWM(self.B_MOTOR_B, 60)

        self.pwm_F_LED = GPIO.PWM( self.F_LED, 100)

        print(" init Ubaba class ")
        self.enable_work_thread = False
        self.is_running_work_thread = False

    
    def start_work(self):
        print("start_work")
        if self.is_running_work_thread == True:
            print("work_thread already running. return ")
            return
        self.enable_work_thread = True
        self.work_thread = threading.Thread( target = self.work, args=(1,))
        self.work_thread.daemon = True
        self.work_thread.start()

    def stop_work(self):
        print("stop_work")
        self.enable_work_thread = False

    def work(self, arg1):
        print("주행쓰레드시작")
        self.is_running_work_thread = True
        count = 0

        self.pwm_F.start(0)
        self.pwm_B.start(0)

        while self.enable_work_thread == True:
            sleep(0.5)
            count = count +1


            # 기어의 상태에 따른 움직임
            # 기어비에 따른 목표속도 설정. 


            # 가속중인지에따라 현재 속도를 목료속도로 증가 
            self.target_duty = self.gear_duty[ self.gear ]
#            print("current duty:{} target_duty:{} acceleration_rate:{}".format( self.current_duty, self.target_duty, self.acceleration_rate ));

            # 현재속도가 목표속도보다 낮은 경우             
            if self.current_duty < self.target_duty:
                if self.acceleration == True:
                    # 가속중이라면 가속 비율만큼 가속한다 
                    self.current_duty = self.current_duty + self.acceleration_rate
                else:
                    # 가속중이 아니라면 감속한다
                    if self.current_duty > 0:
                        self.current_duty = self.current_duty - self.reduction_rate            
            else:
                # 현재속도가 목표속도보다 높은 경우, 목표속도까지 감속한다. 
                self.current_duty = self.current_duty - self.reduction_rate                 
            # 브레이크시 현재속도 초기화
            if self.brake == True:
                self.current_duty = 0

            if self.current_duty < 0:
                self.current_duty = 0

            if self.gear != -1:
                # pwm에 현재속도 duty비 적용
                self.pwm_F.start(0)
                self.pwm_B.stop()
                self.pwm_F.ChangeDutyCycle( self.current_duty )  
                self.pwm_B.ChangeDutyCycle( 0 )  
                GPIO.output( self.F_MOTOR_A, False )

            elif self.gear == -1:
                self.pwm_F.stop()
                self.pwm_B.start(0)
                self.pwm_F.ChangeDutyCycle( 90 )  
                self.pwm_B.ChangeDutyCycle( self.current_duty )  
                GPIO.output( self.F_MOTOR_B, False )
               

        print("주행쓰레드종료")
        self.is_running_work_thread = False


    def f_led(self, onoff, level = 1):
        print(" F_LED onoff:{} level:{}".format(onoff, level))
        if onoff == True:
            self.pwm_F_LED.start(0)
            self.pwm_F_LED.ChangeDutyCycle(20 * level)
        else:
            self.pwm_F_LED.ChangeDutyCycle(100)
            self.pwm_F_LED.stop()
            sleep(0.1)
            GPIO.setup( self.F_LED, GPIO.OUT )
            GPIO.output( self.F_LED, True )
            
    def start_f_led_blink(self):
        if self.f_led_thread_running == True:
            print("이미 쓰레드가 실행중입니다.")
            return 
        self.f_led_thread = threading.Thread( target = self.f_led_work, args=(1, 2))
        self.f_led_thread.daemon = True
        self.f_led_thread.start()


    def f_led_work( self, arg1, arg2 ):
        print(" f_led_work ")  
        self.f_led_thread_running = True      
        self.pwm_F_LED.start(0)

        for k in range(0,10):
            for i in range(0, 100, 5):
                self.pwm_F_LED.ChangeDutyCycle(100-i)
                sleep(0.01)
            for i in range(0, 100, 5):
                self.pwm_F_LED.ChangeDutyCycle(i)
                sleep(0.01)

        self.pwm_F_LED.ChangeDutyCycle(100)
        self.pwm_F_LED.stop()
        sleep(0.1)

        GPIO.setup( self.F_LED, GPIO.OUT )
        GPIO.output( self.F_LED, True )
        self.f_led_thread_running = False
        print(" f_led_work ended ")

    def motor_forward(self, duty= 40):        
        print("motor forward")
        GPIO.output( self.F_MOTOR_B, False )
        self.pwm_B.start(duty)
        self.pwm_B.ChangeDutyCycle(duty)       
        pass
    
    def motor_backward(self, duty = 30):
        print("motor backward")
        GPIO.output( self.F_MOTOR_A, False )
        self.pwm_F.start(duty)
        self.pwm_F.ChangeDutyCycle(duty)       
        pass

    def motor_stop(self):
        print("motor stop")        
        GPIO.output( self.F_MOTOR_A, False )
        GPIO.output( self.F_MOTOR_B, False )        
        self.pwm_F.stop()
        self.pwm_B.stop()
        pass


    def turn_left(self, duty = 100):
        GPIO.output( self.B_MOTOR_A, False )
        self.pwm_R.start(duty)
        self.pwm_R.ChangeDutyCycle(duty)       
        pass

    def turn_right(self, duty = 100):
        GPIO.output( self.B_MOTOR_B, False )
        self.pwm_L.start(duty)
        self.pwm_L.ChangeDutyCycle(duty)       
        pass 

    def turn_center(self):
        GPIO.output( self.B_MOTOR_A, False )
        GPIO.output( self.B_MOTOR_B, False )
        self.pwm_L.stop()
        self.pwm_R.stop()
        pass
    
    def warming_up(self):
        self.motor_stop()
        sleep(0.1)
        self.motor_forward()
        sleep(0.2)
        self.motor_backward()
        sleep(0.2)
        self.motor_stop()
        sleep(0.1)
        self.turn_left()
        sleep(0.1)
        self.turn_center()
        sleep(0.1)
        self.turn_right()
        sleep(0.1)
        self.turn_center()
        return


ubaba = Ubaba()
ubaba.motor_stop()
ubaba.warming_up()

@app.route('/work_thread_enable', methods=['POST'])
def work_therad_enable():
    enable = request.form['enable']
    print(" enable : {}".format(enable))
    if enable == 'true':
        ubaba.start_work()
    else:
        ubaba.stop_work()
    
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/get_status', methods=['POST'])
def get_status():
    data = {
        'is_running_work_thread': ubaba.is_running_work_thread,
        'acceleration': ubaba.acceleration,
        'brake': ubaba.brake, 
        'gear': ubaba.gear,
        'acceleration_rate': ubaba.acceleration_rate, 
        'reduction_rate': ubaba.reduction_rate, 
        'direction': ubaba.direction,
        'current_duty': ubaba.current_duty, 
        'target_duty': ubaba.target_duty } 
    return jsonify(data)

@app.route('/gear', methods=['POST'])
def gear():

    gear_val = int(request.form['gear_value'])
    ubaba.gear = gear_val

    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/acceleration', methods=['POST'])
def acceleration():
    ubaba.acceleration = (request.form['onoff'] == 'true')
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/brake', methods=['POST'])
def brake():
    ubaba.brake = (request.form['onoff'] == 'true')
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
    

@app.route('/headlight', methods=['POST'])
def headlight():
    onoff = request.form['turnon']
    ubaba.f_led(onoff == '0')
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/blink_led', methods=['POST'])
def blink_led():
    interval = float(request.form['interval'])
    count = int(request.form['count'])

    ubaba.start_f_led_blink()
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}


@app.route('/motor', methods=['POST'])
def motor():
    GPIO.setmode(GPIO.BOARD)  
    run = request.form['run']
    turn = request.form['turn']
    if run == 'forward':
        ubaba.motor_backward(60)
    elif run == 'backward':
        ubaba.motor_forward(60)
    elif run == 'stop':
        ubaba.motor_stop()            


    if turn == 'left':
        ubaba.turn_left()
        sleep(0.5)
        ubaba.turn_center()
    elif turn == 'right':
        ubaba.turn_right()
        sleep(0.5)
        ubaba.turn_center()        
    elif turn == 'center':
        ubaba.turn_center()        
        
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/run', methods=['POST'])
def run():
    duty = float(request.form['duty'])
    print("run. duty:", duty )
    ubaba.motor_forward(duty)
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/stop', methods=['POST'])
def stop():
    ubaba.motor_stop()
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'}

@app.route('/view_stream')
def view_stream():
	return render_template('view_stream.html') 

def gen(camera):
    print("hasiho init!!!!!!");
    while True:
        frame = camera.get_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
	ret = Response(gen(Camera()), mimetype='multipart/x-mixed-replace; boundary=frame')
	print(ret)
	return ret

@app.route('/')
def index_page():
    # init_gpio()

    GPIO.setmode(GPIO.BOARD)
    GPIO.setup( F_MOTOR_B, GPIO.OUT )
    GPIO.output( F_MOTOR_B, False )

    GPIO.setup( F_MOTOR_A, GPIO.OUT )
    pwm = GPIO.PWM( F_MOTOR_A, 30 )
    pwm.start( 30 )    


    return render_template('index.html') 

if __name__ == '__main__':
    app.run(use_reloader=True, debug=True, host='0.0.0.0')


