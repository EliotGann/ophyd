


import time
import logging
import pytest
from copy import copy

import epics
from ophyd import (EpicsMotor, Signal, EpicsSignalRO, Component as C)

logger = logging.getLogger(__name__)

@pytest.fixture(scope='function')
def motor():
    sim_pv = 'XF:31IDA-OP{Tbl-Ax:X1}Mtr'

    m = TestEpicsMotor(sim_pv, name='epicsmotor', settle_time=0.1)
    print('epicsmotor', m)
    m.wait_for_connection()
    return m


class TestEpicsMotor(EpicsMotor):
    motor_at_high_limit_switch = C(Signal, value=0)
    motor_at_low_limit_switch = C(Signal, value=0)
    motor_direction_of_travel = C(Signal, value=0)
    motor_high_limit_value = C(EpicsSignalRO, '.HLM')
    motor_low_limit_value = C(EpicsSignalRO, '.LLM')

def almostEqual(x, y, places=7):
    assert round(x-y, places) == 0

def test_connected(motor):
    assert(motor.connected)


def test_limits(motor):
    device_limits = (motor.motor_low_limit_value.get(), motor.motor_high_limit_value.get())
    assert(motor.limits == device_limits)

def test_checkvalue(motor):
    motor.check_value(0)
    
def test_move(motor):
    m = motor
 
    m.stop()
    logger.debug('Move to 0.0')
    m.move(0.0, timeout=5, wait=True)
    time.sleep(0.1)
    almostEqual(m.position, 0.0)

    assert m.settle_time == 0.1    

    logger.debug('Move to 0.1')
    m.move(0.1, timeout=5, wait=True)
    time.sleep(0.1)
    almostEqual(m.position, 0.1)

    logger.debug('Move to 0.1, again')
    m.move(0.1, timeout=5, wait=True)
    time.sleep(0.1)
    almostEqual(m.position, 0.1)

    logger.debug('Move to 0.0')
    m.move(0.0, timeout=5, wait=True)
    time.sleep(0.1)
    almostEqual(m.position, 0.0)

def test_copy(motor):
    m = motor

    repr(m)
    str(m)

    mc = copy(m)
    assert(mc.prefix == m.prefix)

    res = m.move(0.2, wait=False)

    while not res.done:
        time.sleep(0.1)

    time.sleep(0.1)
    assert(res.settle_time == 0.1)
    almostEqual(m.position, 0.2)
    
    m.settle_time = 0.2
    assert(m.settle_time == 0.2)

    assert(res.done)
    almostEqual(res.error, 0)
    assert(res.elapsed > 0)

def test_read(motor):
    m = motor
    m.read()


def test_report(motor):
    m = motor
    m.report

def test_calibration(motor):
    m = motor
    m.user_offset.put(0, wait=True)

    # Calibration
    old_position = m.position
    expected_offset = 10-m.position
    m.set_current_position(10)
    assert(not m.offset_frozen)
    assert(m.position == 10)
    assert(m.offset == expected_offset)
    m.set_current_position(old_position)

def test_high_limit_switch(motor):
    m = motor

    # limit switch status
    m.motor_direction_of_travel.put(1)
    res = m.move(1, wait=False)
    m.motor_at_high_limit_switch.put(1)

    while not res.done:
        time.sleep(0.1)

    assert(not res.success)
    assert(m.at_high_limit_switch)

    m.motor_at_high_limit_switch.put(0)


def test_low_limit_switch(motor):
    m = motor
    m.motor_direction_of_travel.put(0)
    res = m.move(0, wait=False)
    m.motor_at_low_limit_switch.put(1)

    while not res.done:
        time.sleep(0.1)

    assert(not res.success)
    assert(m.at_low_limit_switch)
    m.motor_at_low_limit_switch.put(0)

def test_low_limit_switch_while_moving_out(motor):
    m = motor

    # If the Motor is at the Low Limit Switch
    # all the movements in the opposite
    # direction must be success=True
    m.motor_direction_of_travel.put(1)
    m.motor_at_low_limit_switch.put(1)
    res = m.move(1, wait=False)

    while not res.done:
        time.sleep(0.1)

    assert(m.at_low_limit_switch)
    assert(res.success)
    m.motor_at_low_limit_switch.put(0)

def test_high_limit_switch_while_moving_out(motor):
    m = motor

    # If the Motor is at the High Limit Switch
    # all the movements in the opposite
    # direction must be success=True
    m.motor_direction_of_travel.put(0)
    m.motor_at_high_limit_switch.put(1)
    res = m.move(0, wait=False)

    while not res.done:
        time.sleep(0.1)

    assert(m.at_high_limit_switch)
    assert(res.success)
    m.motor_at_high_limit_switch.put(0)

def test_homing_forward(motor):
    m = motor

    # homing forward
    m.move(-1, wait=True)
    res = m.home("forward", timeout=2, wait=False)

    while not res.done:
        time.sleep(0.1)

    # MotorSim is unable to execute homing
    assert(not res.success)
    m.stop()


def test_homing_reverse(motor):
    m = motor
    # homing reverse
    m.move(1, wait=True)
    res = m.home("reverse", timeout=2, wait=False)

    while not res.done:
        time.sleep(0.1)

    assert(not res.success)
    m.stop()

def test_homing_invalid(motor):
    with pytest.raises(ValueError):
        m = motor
        # homing reverse
        m.move(1, wait=True)
        res = m.home("foobar", timeout=2, wait=False)

        while not res.done:
            time.sleep(0.1)

        assert(not res.success)
        m.stop()

