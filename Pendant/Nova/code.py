import time
import math
import random
import board
import touchio
import analogio
import digitalio
import neopixel
import adafruit_fancyled.adafruit_fancyled as fancy

# This is the red LED next to the power switch
led_pin = board.D13
led = digitalio.DigitalInOut(led_pin)
led.direction = digitalio.Direction.OUTPUT

# DotStart is the single RGB light on the back of the board, by the reset button
# On the Gemma M0 it's connected to the the SPI interface
try:
    import adafruit_dotstar
    dotstar_len = 1
    dotstar_sck = board.APA102_SCK
    dotstar_mosi = board.APA102_MOSI
    dotstar = adafruit_dotstar.DotStar(dotstar_sck, dotstar_mosi, dotstar_len, brightness=1.0, auto_write=True)
except ImportError:
    dotstar = None

# Capacitive touch sensor on pin A0/D1
# This pin can do lots of other things too, but this lets you get a button with no extra hardware
touch_pin = board.A0
touch = touchio.TouchIn(touch_pin)

# NeoPixels are the main lights in the pendant
# There are 14 of them, arranged in two rings of 7
#   Lower ring: Pixels 0-6
#   Upper ring: Pixels 7-13
# Inside each ring:
#   Pixel 0: Center
#   Pixel 1: Above and to the right of center
#   Pixels 2-6: Clockwise around the ring
# The Gemma M0 D0 output supports DMA for Neopixels, but not in Python
# If you swtich to native Arduino try this: https://learn.adafruit.com/dma-driven-neopixels
ring_len = 7
neopixel_len = ring_len * 2
neopixel_pin = board.D0
neopixel = neopixel.NeoPixel(neopixel_pin, neopixel_len, brightness=1.0, auto_write=False)
# Noepixels don't light if scaled below this value
neopixel_min = 0.0045

# Analog light sensor GA1A12S202
sensor_pin = board.A1
sensor = analogio.AnalogIn(sensor_pin)
# The raw analog sample scale is 2^16, but the sensor can't quite use that whole range
# GA1A12S202 can output about 2k to 60k, logarithmic (which is useful, since eyes are also log-ish)
sensor_min = 2000
sensor_max = 60000
sensor_range = sensor_max - sensor_min

def neopixel_limits(value):
    value = min(1.0, value)
    if (value > neopixel_min):
        value = max(neopixel_min, value)
    else:
        value = 0.0
    return value

def scale():
    return 1.0
    # Override to full brightnes if the button is pushed
    led.value = touch.value
    if (touch.value):
        scale = 1.0
    else:
        # Normalize (0.0 - 1.0)
        scale = (sensor.value - sensor_min) / sensor_range
        # Use an exponent to make the scale more sensitive at the low ends
        # Because this value is normalized squaring always makes it smaller (unless you're at 100%)
        scale = scale ** 2
        # Enforce a minimum to avoid blackouts at low ambient light levels
        scale = neopixel_limits(scale)
    return scale

def decay(value, step, rate):
    v = value * (rate ** step)
    v = neopixel_limits(v)
    return v

def ring_move(start, move):
    target = start + move
    if (target % ring_len == 0):
        if (move < 0):
            target -= 1
        else:
            target -= ring_len - 1
    if (int(target / ring_len) < int(start / ring_len)):
        target += ring_len
    if (target >= neopixel_len):
        target -= ring_len
    if (target < 0):
        target += ring_len
    return target

def ring_center(start):
    target = int(start / ring_len) * ring_len
    return target

# Inter-step delay
delay = 0.015
# 0.0-1.0, bigger numbers decay slower
fade_rate = 0.96
ramp_rate = 0.80
# Total steps in the fade/ramp
ramp_steps = 10
fade_steps = 80
# Speed/color adjustments for side pixels
side_delay = int(ramp_steps * 0.5)
side_value_scale = 0.25
side_ramp_scale = 0.975
side_hue_offset = 0.08
side_sat = 0.85
# Color
hue_max = 0.73
hue_min = 0.42

# Math to make the code easier
ramp_index = ramp_steps + 1
side_index = ramp_index + side_delay
total_steps = ramp_index + fade_steps
last_step = total_steps - 1
while True:
    # Pick a ring pixel other than center
    pixel = None
    while (pixel == None or pixel % ring_len == 0):
        pixel = random.randint(0, neopixel_len - 1)

    # Pick a related set of colors, scaled to the current brightness
    hue = random.uniform(hue_max, hue_min)
    color = fancy.CHSV(hue, 1.0, scale())
    color_l = fancy.CHSV(hue - side_hue_offset, side_sat, color.value)
    color_r = fancy.CHSV(hue + side_hue_offset, side_sat, color.value)
    color_c = fancy.CHSV(hue, side_sat, color.value)

    for i in range(0, total_steps):
        # Primary pixel
        if (i <= ramp_index):
            v = decay(color.value, (ramp_steps - i), ramp_rate)
            c = fancy.CHSV(color.hue, color.saturation, v)
            neopixel[pixel] = c.pack()
        elif (i == last_step):
            neopixel[pixel] = 0
        else:
            v = decay(color.value, i - ramp_steps, fade_rate)
            c = fancy.CHSV(color.hue, color.saturation, v)
            neopixel[pixel] = c.pack()

        # Side pixels
        if (i >= side_delay and i < side_index):
            s = ramp_steps + side_delay - i
            v = decay(color.value * side_value_scale, s, ramp_rate * side_ramp_scale)
            c_l = fancy.CHSV(color_l.hue, color_l.saturation, v)
            c_r = fancy.CHSV(color_r.hue, color_r.saturation, v)
            c_c = fancy.CHSV(color_c.hue, color_c.saturation, v)
            neopixel[ ring_move(pixel, -1) ] = c_l.pack()
            neopixel[ ring_move(pixel, 1) ] = c_r.pack()
            neopixel[ ring_center(pixel) ] = c_c.pack()
        elif (i < side_delay or i == last_step):
            neopixel[ ring_move(pixel, -1) ] = 0
            neopixel[ ring_move(pixel, 1) ] = 0
            neopixel[ ring_center(pixel) ] = 0
        else:
            s = i - side_delay
            v = decay(color.value * side_value_scale, s, fade_rate * side_ramp_scale)
            c_l = fancy.CHSV(color_l.hue, color_l.saturation, v)
            c_r = fancy.CHSV(color_r.hue, color_r.saturation, v)
            c_c = fancy.CHSV(color_c.hue, color_c.saturation, v)
            neopixel[ ring_move(pixel, -1) ] = c_l.pack()
            neopixel[ ring_move(pixel, 1) ] = c_r.pack()
            neopixel[ ring_center(pixel) ] = c_c.pack()

        # Push to hardware
        neopixel.show()
        time.sleep(delay)

    time.sleep(1.5)